"""Debug-only patch: make the MXFP4-CPU dequant respect the model's
configured dtype instead of hardcoding bf16.

In fix7, ``_process_weights_for_cpu`` hardcoded ``.to(torch.bfloat16)`` at the
end of the dequant. That's fine while ``--dtype bfloat16`` is the only
supported mode (it is upstream, for mxfp4), but it crashes when we relax the
constraint via fix9-debug + ``--dtype half`` because the dequantized weights
end up bf16 while the rest of the activations are fp16 — matmul rejects the
dtype mismatch.

This patch reads ``MXFP4_OUT_DTYPE`` from the environment (one of "bfloat16"
| "float16" | "float32"; default "bfloat16") and uses that as the output
dtype. Combined with fix9-debug's ``ALLOW_FP32_MXFP4=1``, this lets us A/B
bf16 vs fp16 vs fp32 for the Phase 2 precision investigation without
further image rebuilds.

This patch is intended for diagnostic builds only.
"""

import sys
from pathlib import Path

F = Path(
    "/opt/.venv/lib/python3.12/site-packages/sglang/srt/layers/quantization/mxfp4.py"
)
src = F.read_text()
original = src

# The fix7 dequant has two hardcoded `.to(torch.bfloat16)` (one in the
# helper return, one in the param replacement). Replace both with a
# call to a tiny helper that reads the env var.
old1 = (
    "            out = (values * scale_f).view(*batch_dims, K).to(torch.bfloat16)\n"
    "            return out\n"
)
new1 = (
    "            import os as _os\n"
    "            _dt = {\n"
    "                'bfloat16': torch.bfloat16,\n"
    "                'float16':  torch.float16,\n"
    "                'half':     torch.float16,\n"
    "                'float32':  torch.float32,\n"
    "            }.get(_os.environ.get('MXFP4_OUT_DTYPE', 'bfloat16').lower(), torch.bfloat16)\n"
    "            out = (values * scale_f).view(*batch_dims, K).to(_dt)\n"
    "            return out\n"
)

if old1 not in src:
    print("ERROR: dequant inner return anchor not found", file=sys.stderr)
    sys.exit(1)
src = src.replace(old1, new1)

if src == original:
    print("ERROR: nothing was patched", file=sys.stderr)
    sys.exit(1)

F.write_text(src)
print(f"Patched {F}")
