"""Patch gpt_oss.py to make its weight-loading paths CPU-safe.

The model file hard-codes a handful of `.cuda()` / `torch.cuda.*` calls
in the MXFP4 weight loader and the dequant helper. On a CPU-only torch
those fail with `AssertionError: Torch not compiled with CUDA enabled`.

We guard each call so it becomes a no-op on CPU and behaves exactly as
before on a CUDA host.

Patched call sites:
  - _load_mxfp4_experts_weights:   weight = weight.cuda()
  - set_embed_and_head:            torch.cuda.empty_cache(); torch.cuda.synchronize()
  - _dequant_mlp_weight:           w_blocks = w_blocks.cuda(); w_scales = w_scales.cuda()
"""

import sys
from pathlib import Path

F = Path(
    "/opt/.venv/lib/python3.12/site-packages/sglang/srt/models/gpt_oss.py"
)
src = F.read_text()
original = src

substitutions = [
    # _load_mxfp4_experts_weights: weight = weight.cuda()
    (
        "        for name, weight in weights:\n"
        "            weight = weight.cuda()\n",
        "        for name, weight in weights:\n"
        "            if torch.cuda.is_available():\n"
        "                weight = weight.cuda()\n",
    ),
    # set_embed_and_head: torch.cuda.empty_cache / synchronize
    (
        "        self.lm_head.weight = head\n"
        "        torch.cuda.empty_cache()\n"
        "        torch.cuda.synchronize()\n",
        "        self.lm_head.weight = head\n"
        "        if torch.cuda.is_available():\n"
        "            torch.cuda.empty_cache()\n"
        "            torch.cuda.synchronize()\n",
    ),
    # _dequant_mlp_weight: w_blocks / w_scales .cuda()
    (
        "    w_blocks = w_blocks.cuda()\n"
        "    w_scales = w_scales.cuda()\n",
        "    if torch.cuda.is_available():\n"
        "        w_blocks = w_blocks.cuda()\n"
        "        w_scales = w_scales.cuda()\n",
    ),
]

for needle, replacement in substitutions:
    if needle not in src:
        print(
            f"ERROR: patch site not found:\n---\n{needle}---",
            file=sys.stderr,
        )
        sys.exit(1)
    src = src.replace(needle, replacement)

if src == original:
    print("ERROR: nothing was patched", file=sys.stderr)
    sys.exit(1)

F.write_text(src)
print(f"Patched {F}")
