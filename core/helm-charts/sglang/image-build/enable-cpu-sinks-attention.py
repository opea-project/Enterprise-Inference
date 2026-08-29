"""Add sinks-attention forward support to torch_native_backend.

gpt-oss uses sink attention (a learnable per-head scalar added to the softmax
denominator). sglang's GPU kernels (triton, fa3, trtllm_mha, aiter) accept a
`sinks` kwarg in their `forward_extend` / `forward_decode`, but none of the
CPU backends do (`intel_amx`, `torch_native`).

This patch teaches `TorchNativeAttnBackend` to accept and apply sinks. The
math is exactly what sglang's own triton kernel does
(see srt/layers/attention/triton_ops/extend_attention.py lines 535-537):

    deno += exp(cur_sink - e_max)

i.e. a fake extra "row" with logit = sinks[h] is included in the softmax
denominator but excluded from the value-weighted sum. With sinks the
attention probabilities sum to <1.

Implementation: when sinks is provided, bypass PyTorch's SDPA (which has no
sinks API) and do attention manually in ~15 lines. Falls back to SDPA fast
path when sinks is None (zero perf cost for non-sink models).
"""

import sys
from pathlib import Path

F = Path(
    "/opt/.venv/lib/python3.12/site-packages/sglang/srt/layers/attention/torch_native_backend.py"
)
src = F.read_text()
original = src

# 1) Add sinks=None kwarg to forward_extend and forward_decode signatures, and
#    plumb it through to the SDPA wrapper.
src = src.replace(
    "    def forward_extend(\n"
    "        self,\n"
    "        q,\n"
    "        k,\n"
    "        v,\n"
    "        layer: RadixAttention,\n"
    "        forward_batch: ForwardBatch,\n"
    "        save_kv_cache=True,\n"
    "    ):\n",
    "    def forward_extend(\n"
    "        self,\n"
    "        q,\n"
    "        k,\n"
    "        v,\n"
    "        layer: RadixAttention,\n"
    "        forward_batch: ForwardBatch,\n"
    "        save_kv_cache=True,\n"
    "        sinks=None,\n"
    "    ):\n"
    "        self._sinks = sinks\n",
)

src = src.replace(
    "    def forward_decode(\n"
    "        self,\n"
    "        q,\n"
    "        k,\n"
    "        v,\n"
    "        layer: RadixAttention,\n"
    "        forward_batch: ForwardBatch,\n"
    "        save_kv_cache=True,\n"
    "    ):\n",
    "    def forward_decode(\n"
    "        self,\n"
    "        q,\n"
    "        k,\n"
    "        v,\n"
    "        layer: RadixAttention,\n"
    "        forward_batch: ForwardBatch,\n"
    "        save_kv_cache=True,\n"
    "        sinks=None,\n"
    "    ):\n"
    "        self._sinks = sinks\n",
)

# 2) Replace the SDPA call(s) inside _run_sdpa_forward_extend / _run_sdpa_forward_decode
#    with our sinks-aware wrapper. The wrapper is appended as a module-level
#    function and the existing call sites are routed through it.
#
# We do this by injecting a helper function near the top of the module and
# monkey-patching torch.nn.functional.scaled_dot_product_attention's local
# import to point at it inside this file. Cleanest: append the helper, then
# swap the SDPA call inside the class methods.

# Inject the wrapper right after the existing imports block.
WRAPPER = '''

# ---- sinks-aware SDPA wrapper (added by enable-cpu-sinks-attention.py) ----
import math as _math
def _sdpa_with_sinks(query, key, value, *, attn_mask=None, dropout_p=0.0,
                     is_causal=False, scale=None, enable_gqa=False,
                     sinks=None):
    """Forward-only scaled_dot_product_attention with optional sinks.

    When sinks is None this is equivalent to torch's SDPA.
    When sinks is a (H,) tensor of per-head scalars, the softmax denominator
    is augmented by exp(sinks[h] - row_max) — i.e. an attention sink.
    """
    if sinks is None:
        return torch.nn.functional.scaled_dot_product_attention(
            query, key, value,
            attn_mask=attn_mask, dropout_p=dropout_p,
            is_causal=is_causal, scale=scale, enable_gqa=enable_gqa,
        )

    # Manual attention path with sinks
    # query/key/value: (B, H_q, Sq, D) and (B, H_kv, Sk, D)
    if scale is None:
        scale = 1.0 / _math.sqrt(query.shape[-1])

    if enable_gqa and key.shape[-3] != query.shape[-3]:
        # repeat KV heads to match Q heads
        rep = query.shape[-3] // key.shape[-3]
        key = key.repeat_interleave(rep, dim=-3)
        value = value.repeat_interleave(rep, dim=-3)

    # scores: (B, H, Sq, Sk)
    scores = torch.matmul(query, key.transpose(-2, -1)) * scale

    if is_causal:
        Sq, Sk = scores.shape[-2], scores.shape[-1]
        causal_mask = torch.ones(Sq, Sk, dtype=torch.bool, device=scores.device).tril(
            diagonal=Sk - Sq
        )
        scores = scores.masked_fill(~causal_mask, float("-inf"))
    if attn_mask is not None:
        if attn_mask.dtype == torch.bool:
            scores = scores.masked_fill(~attn_mask, float("-inf"))
        else:
            scores = scores + attn_mask

    # Stable softmax with sinks
    row_max = scores.amax(dim=-1, keepdim=True)
    row_max = row_max.masked_fill(row_max == float("-inf"), 0.0)
    exp_scores = torch.exp(scores - row_max)
    # sinks: (H,) -> broadcast to (1, H, 1) so sink_exp is (B, H, Sq)
    sinks_t = sinks.to(scores.dtype).to(scores.device).view(1, -1, 1)
    sink_exp = torch.exp(sinks_t - row_max.squeeze(-1))
    denom = exp_scores.sum(dim=-1) + sink_exp  # (B, H, Sq)
    attn_weights = exp_scores / denom.unsqueeze(-1)
    if dropout_p > 0.0:
        attn_weights = torch.nn.functional.dropout(attn_weights, p=dropout_p)
    return torch.matmul(attn_weights, value)
# ---- end sinks wrapper ----
'''

# Place the wrapper just after the last `from ... import ...` block. Simple anchor.
anchor_for_wrapper = "class TorchNativeAttnBackend(AttentionBackend):"
if anchor_for_wrapper not in src:
    print("ERROR: class anchor not found", file=sys.stderr)
    sys.exit(1)
src = src.replace(
    anchor_for_wrapper,
    WRAPPER + "\n" + anchor_for_wrapper,
    1,
)

# 3) Route the existing SDPA calls through _sdpa_with_sinks with the stored sink.
#    The class has at least two call sites for `scaled_dot_product_attention`
#    inside _run_sdpa_forward_extend / _run_sdpa_forward_decode. Both fully-
#    qualified and bare-name (imported) forms appear. Rewrite both.
src = src.replace(
    "torch.nn.functional.scaled_dot_product_attention(",
    "_sdpa_with_sinks(",
)
# The bare form: the file does `from torch.nn.functional import scaled_dot_product_attention`
# and calls it directly. Match those too. Use a word boundary via the preceding
# whitespace + name to avoid matching the import line itself.
import re as _re
src = _re.sub(
    r"(?<![\w.])scaled_dot_product_attention\(",
    "_sdpa_with_sinks(",
    src,
)
# Note: the original `from torch.nn.functional import scaled_dot_product_attention`
# import line still exists but is now unused. Harmless.

# 4) Inject `sinks=getattr(self, "_sinks", None)` into the wrapper invocation.
#    Easiest: when _run_sdpa_forward_extend/decode call _sdpa_with_sinks, they
#    don't pass sinks. We need to pass it. We patch _run_sdpa_forward_* to
#    forward self._sinks.
#
#    The cleanest sed: at every `_sdpa_with_sinks(...)` call inside this file
#    that occurs in a method of TorchNativeAttnBackend, add sinks=self._sinks
#    as the final kwarg. We do this by finding `enable_gqa=enable_gqa,\n        is_causal=causal,\n    )` pattern (the common closing of the SDPA call)
#    and inserting `sinks=self._sinks` before the `)`.

needle_close = (
    "                    enable_gqa=enable_gqa,\n"
    "                    scale=scaling,\n"
    "                    is_causal=causal,\n"
    "                )\n"
)
replacement_close = (
    "                    enable_gqa=enable_gqa,\n"
    "                    scale=scaling,\n"
    "                    is_causal=causal,\n"
    "                    sinks=getattr(self, \"_sinks\", None),\n"
    "                )\n"
)
if needle_close not in src:
    print(
        "ERROR: SDPA close-pattern not found inside torch_native_backend.\n"
        "  We tried to anchor on the 4-space + closing-paren pattern; the file shape may have changed.",
        file=sys.stderr,
    )
    sys.exit(1)
src = src.replace(needle_close, replacement_close)

if src == original:
    print("ERROR: nothing was patched", file=sys.stderr)
    sys.exit(1)

F.write_text(src)
print(f"Patched {F}")
