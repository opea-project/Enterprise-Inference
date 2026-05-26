"""Debug-only patch: remove sglang's hard override that forces dtype=bfloat16
for mxfp4 models.

In `server_args.py` the GptOss branch contains:

    if is_mxfp4_quant_format:
        # use bf16 for mxfp4 triton kernels
        self.dtype = "bfloat16"

That's correct for the GPU path (the triton mxfp4 kernels only accept bf16
inputs), but it also fires on CPU and prevents us from running an fp32
forward to A/B against the bf16 path for precision-drift investigation.

This patch makes the override conditional on the user NOT having explicitly
chosen a dtype. If the launcher was invoked with `--dtype float32`, we
respect that choice.

This patch is intended for diagnostic builds only — it does NOT belong in
a production image. It is gated behind the ALLOW_FP32_MXFP4=1 env var so
the override remains in effect for normal deployments.
"""

import sys
from pathlib import Path

F = Path(
    "/opt/.venv/lib/python3.12/site-packages/sglang/srt/server_args.py"
)
src = F.read_text()
original = src

needle = (
    "            if is_mxfp4_quant_format:\n"
    "                # use bf16 for mxfp4 triton kernels\n"
    "                self.dtype = \"bfloat16\"\n"
)
replacement = (
    "            if is_mxfp4_quant_format:\n"
    "                # use bf16 for mxfp4 triton kernels (CPU debug bypass via ALLOW_FP32_MXFP4=1)\n"
    "                import os as _os\n"
    "                if _os.getenv(\"ALLOW_FP32_MXFP4\", \"0\") != \"1\":\n"
    "                    self.dtype = \"bfloat16\"\n"
    "                elif self.dtype in (None, \"auto\"):\n"
    "                    self.dtype = \"bfloat16\"\n"
)

if needle not in src:
    print("ERROR: mxfp4 dtype-override anchor not found", file=sys.stderr)
    sys.exit(1)
src = src.replace(needle, replacement)

if src == original:
    print("ERROR: nothing was patched", file=sys.stderr)
    sys.exit(1)

F.write_text(src)
print(f"Patched {F}")
