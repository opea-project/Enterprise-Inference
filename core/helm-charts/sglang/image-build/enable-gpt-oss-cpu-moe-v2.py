"""Reroute Mxfp4MoEMethod's CPU forward through sglang's reference
``moe_forward_native`` instead of ``fused_experts_cpu``.

After fix7 we got gpt-oss-20b past dequant with sane numerics (low_first
nibble order), but the output was still gibberish. The cause: gpt-oss uses
a custom Swish-GLU activation:

    gate, up = x[..., ::2], x[..., 1::2]            # INTERLEAVED gate/up
    gate = gate.clamp(max=gemm1_limit)
    up   = up.clamp(min=-gemm1_limit, max=gemm1_limit)
    out  = gate * sigmoid(gate * gemm1_alpha) * (up + 1)

plus per-expert biases on both W13 and W2. ``fused_experts_cpu`` only
implements plain ``silu(gate) * up`` with no alpha, no clamp, no biases.

sglang already has a pure-PyTorch reference that handles all of this:
``sglang.srt.layers.moe.fused_moe_native.moe_forward_native``. It calls
``swiglu_gpt_oss_sigmoid_alpha`` (pure torch with @torch.compile) when
``gemm1_alpha`` is set, and adds W13/W2 biases when present on the layer.

This patch:

1. Removes the ``_amx_process_weight_after_loading`` call from
   ``_process_weights_for_cpu`` — we no longer need AMX-packed weights
   because ``moe_forward_native`` uses ``F.linear`` and ``torch.einsum``
   on plain bf16 weights.
2. Rewrites ``forward_cpu`` to delegate to ``moe_forward_native``.
"""

import re
import sys
from pathlib import Path

F = Path(
    "/opt/.venv/lib/python3.12/site-packages/sglang/srt/layers/quantization/mxfp4.py"
)
src = F.read_text()
original = src

# 1. Strip the AMX-pack call from _process_weights_for_cpu.
src = src.replace(
    "        _amx_process_weight_after_loading(layer, [\"w13_weight\", \"w2_weight\"])\n",
    "        # _amx_process_weight_after_loading skipped: moe_forward_native uses\n"
    "        # plain F.linear / einsum, which expect un-packed (E, OUT, IN) bf16.\n",
)

# 2. Replace the body of forward_cpu with a delegation to moe_forward_native.
#    Anchor on the full forward_cpu added by fix4's enable-gpt-oss-cpu-moe.py.
old_forward = (
    "    def forward_cpu(self, layer, dispatch_output):\n"
    "        \"\"\"Mirrors unquant.py:UnquantizedFusedMoEMethod.forward_cpu.\n"
    "\n"
    "        After _process_weights_for_cpu has run, the layer's weights are\n"
    "        plain bf16 AMX-packed tensors, so the CPU MoE kernel can serve\n"
    "        them with the UNQUANT quant method.\n"
    "        \"\"\"\n"
    "        import torch\n"
    "        from sglang.srt.layers.moe.token_dispatcher import StandardCombineInput\n"
    "        from sglang.srt.layers.moe.topk import apply_topk_weights_cpu\n"
    "        from sglang.srt.layers.amx_utils import CPUQuantMethod\n"
    "\n"
    "        x = dispatch_output.hidden_states\n"
    "        topk_output = dispatch_output.topk_output\n"
    "\n"
    "        topk_weights, topk_ids, _ = topk_output\n"
    "        x, topk_weights = apply_topk_weights_cpu(\n"
    "            self.moe_runner_config.apply_router_weight_on_input,\n"
    "            topk_weights,\n"
    "            x,\n"
    "        )\n"
    "        output = torch.ops.sgl_kernel.fused_experts_cpu(\n"
    "            x,\n"
    "            layer.w13_weight,\n"
    "            layer.w2_weight,\n"
    "            topk_weights,\n"
    "            topk_ids,\n"
    "            False,  # inplace\n"
    "            CPUQuantMethod.UNQUANT,\n"
    "            None,   # w1_scale\n"
    "            None,   # w2_scale\n"
    "            None,   # w1_zp\n"
    "            None,   # w2_zp\n"
    "            None,   # block_size\n"
    "            True,   # is_vnni\n"
    "        )\n"
    "        return StandardCombineInput(hidden_states=output)\n"
)

new_forward = (
    "    def forward_cpu(self, layer, dispatch_output):\n"
    "        \"\"\"CPU MoE forward via moe_forward_native (gpt-oss-aware).\n"
    "\n"
    "        Uses sglang's reference pure-PyTorch MoE forward, which handles:\n"
    "        - W13 / W2 biases (gpt-oss has both)\n"
    "        - The gpt-oss-specific swiglu variant\n"
    "          (interleaved gate/up + sigmoid(alpha * gate) + clamp + (up+1))\n"
    "        when ``moe_runner_config.gemm1_alpha`` is set.\n"
    "        \"\"\"\n"
    "        from sglang.srt.layers.moe.fused_moe_native import moe_forward_native\n"
    "        from sglang.srt.layers.moe.token_dispatcher import StandardCombineInput\n"
    "\n"
    "        output = moe_forward_native(\n"
    "            layer,\n"
    "            dispatch_output.hidden_states,\n"
    "            dispatch_output.topk_output,\n"
    "            self.moe_runner_config,\n"
    "        )\n"
    "        return StandardCombineInput(hidden_states=output)\n"
)

if old_forward not in src:
    print("ERROR: old forward_cpu not found (fix4 may have been changed)",
          file=sys.stderr)
    sys.exit(1)
src = src.replace(old_forward, new_forward)

if src == original:
    print("ERROR: nothing was patched", file=sys.stderr)
    sys.exit(1)

F.write_text(src)
print(f"Patched {F}")
