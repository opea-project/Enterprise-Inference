"""Debug-only patch: promote the per-expert forward inside
``moe_forward_native`` to fp32.

Phase 2 of the gpt-oss-on-CPU investigation showed that long-form generation
drifts into repetition after ~150-200 tokens with bf16 intermediates, and
that switching the whole model to fp16 pushed the drift point ~30% further
out — confirming precision is a real contributor. Option 1 in
REMAINING_WORK.md is the cheapest follow-up: keep the layer's bf16 weights
and KV cache untouched, but promote the per-expert intermediates
(``gate_up``, ``expert_out``, biases, and the weights they're multiplied
against) to fp32 across the per-expert compute, casting back to the layer's
dtype only at the very end of the expert's forward.

Gated behind ``FP32_PROMOTE_MOE=1`` so the patch ships in the image but
costs nothing unless explicitly enabled. With it off, the per-expert path
is byte-identical to upstream.

Intended for diagnostic A/B builds. If Option 1 closes most of the
long-form gap, the right next step is the upstream AMX kernel work
(Option 4); this Python promotion is not how we want to ship in
production because it doubles the per-expert memory bandwidth.
"""

import sys
from pathlib import Path

F = Path(
    "/opt/.venv/lib/python3.12/site-packages/sglang/srt/layers/moe/fused_moe_native.py"
)
src = F.read_text()
original = src

# We replace the entire per-expert body. Match the exact block from upstream
# (current as of v0.5.12). If upstream drifts, the anchor will fail loudly
# rather than silently mis-patch.
old = '''        # Apply w13 linear
        gate_up = F.linear(tokens_for_this_expert, layer_w13_weight)

        # Add bias if present (for models like GPT-OSS)
        if layer_w13_bias is not None:
            gate_up_fp32 = gate_up.float() + layer_w13_bias
            gate_up = gate_up_fp32.to(original_dtype)

        # Apply activation
        if (
            moe_runner_config.activation == "silu"
            and moe_runner_config.gemm1_alpha is not None
        ):
            assert moe_runner_config.gemm1_clamp_limit is not None
            gate_up = swiglu_gpt_oss_sigmoid_alpha(
                gate_up,
                moe_runner_config.gemm1_alpha,
                moe_runner_config.gemm1_clamp_limit,
            )
        else:
            gate_up = act(gate_up)

        # Apply w2 linear
        expert_out = F.linear(gate_up, layer_w2_weight)

        # Add bias if present (for models like GPT-OSS)
        if layer_w2_bias is not None:
            expert_out = expert_out.float() + layer_w2_bias
            expert_out = expert_out.to(original_dtype)

        outputs.append(expert_out)
'''

new = '''        # === fp32-promotion debug patch (FP32_PROMOTE_MOE=1) =================
        # Promote weights, input, biases, and all intermediates to fp32 for
        # this expert's forward. Cast back to original_dtype at the very end
        # so the caller, KV cache, and combine sum all see the layer's
        # native dtype. With the env var off, behavior is byte-identical to
        # upstream.
        import os as _os
        _promote_fp32 = _os.environ.get("FP32_PROMOTE_MOE", "0") == "1"
        if _promote_fp32:
            _toks  = tokens_for_this_expert.float()
            _w13   = layer_w13_weight.float()
            _w2    = layer_w2_weight.float()
            _b13   = layer_w13_bias.float() if layer_w13_bias is not None else None
            _b2    = layer_w2_bias.float()  if layer_w2_bias  is not None else None

            gate_up = F.linear(_toks, _w13)
            if _b13 is not None:
                gate_up = gate_up + _b13

            if (
                moe_runner_config.activation == "silu"
                and moe_runner_config.gemm1_alpha is not None
            ):
                assert moe_runner_config.gemm1_clamp_limit is not None
                # swiglu_gpt_oss_sigmoid_alpha preserves input dtype for its
                # internal math, so passing fp32 keeps the sigmoid + chained
                # multiplies in fp32 (Option 3 lands for free here).
                gate_up = swiglu_gpt_oss_sigmoid_alpha(
                    gate_up,
                    moe_runner_config.gemm1_alpha,
                    moe_runner_config.gemm1_clamp_limit,
                )
            else:
                gate_up = act(gate_up)

            expert_out = F.linear(gate_up, _w2)
            if _b2 is not None:
                expert_out = expert_out + _b2

            expert_out = expert_out.to(original_dtype)
        else:
            # ---- upstream path (unchanged) ----
            gate_up = F.linear(tokens_for_this_expert, layer_w13_weight)
            if layer_w13_bias is not None:
                gate_up_fp32 = gate_up.float() + layer_w13_bias
                gate_up = gate_up_fp32.to(original_dtype)

            if (
                moe_runner_config.activation == "silu"
                and moe_runner_config.gemm1_alpha is not None
            ):
                assert moe_runner_config.gemm1_clamp_limit is not None
                gate_up = swiglu_gpt_oss_sigmoid_alpha(
                    gate_up,
                    moe_runner_config.gemm1_alpha,
                    moe_runner_config.gemm1_clamp_limit,
                )
            else:
                gate_up = act(gate_up)

            expert_out = F.linear(gate_up, layer_w2_weight)
            if layer_w2_bias is not None:
                expert_out = expert_out.float() + layer_w2_bias
                expert_out = expert_out.to(original_dtype)
        # === end fp32-promotion debug patch ===================================

        outputs.append(expert_out)
'''

if old not in src:
    print("ERROR: per-expert forward anchor not found in fused_moe_native.py", file=sys.stderr)
    sys.exit(1)
src = src.replace(old, new)

if src == original:
    print("ERROR: nothing was patched", file=sys.stderr)
    sys.exit(1)

F.write_text(src)
print(f"Patched {F}")
