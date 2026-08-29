"""Patch sglang's quantization/__init__.py to enable MXFP4 on CPU.

The upstream code gates the mxfp4 registration behind is_cuda()/is_hip().
On CPU this prevents loading models with quant_method=mxfp4 (e.g.
openai/gpt-oss-*), even though the model file's CPU-friendly dequantization
path (fp8_utils.dequant_mxfp4 → MXFP4QuantizeUtil.dequantize, pure PyTorch)
is fully functional. This patch widens the gate so mxfp4 is registered
when SGLANG_USE_CPU_ENGINE=1 is set and adds it to the CPU-supported
quantization allowlist.
"""

import re
import sys
from pathlib import Path

INIT = Path(
    "/opt/.venv/lib/python3.12/site-packages/sglang/srt/layers/quantization/__init__.py"
)

src = INIT.read_text()
original = src

# 1) Ensure `os` is imported (we use it to gate behind the env var)
if not re.search(r"^import os\b", src, flags=re.M):
    src = src.replace(
        "import builtins\n",
        "import builtins\nimport os\n",
        1,
    )

# 2) Widen the gate: register mxfp4 also when running with the CPU engine
src = src.replace(
    "if is_cuda() or (_is_mxfp_supported and is_hip()):\n"
    "    BASE_QUANTIZATION_METHODS.update(\n"
    "        {\n"
    '            "mxfp4": Mxfp4Config,\n'
    "        }\n"
    "    )",
    'if is_cuda() or (_is_mxfp_supported and is_hip()) or os.getenv("SGLANG_USE_CPU_ENGINE", "0") == "1":\n'
    "    BASE_QUANTIZATION_METHODS.update(\n"
    "        {\n"
    '            "mxfp4": Mxfp4Config,\n'
    "        }\n"
    "    )",
)

# 3) Add mxfp4 to the CPU allowlist so get_quantization_config() returns it
src = src.replace(
    "CPU_QUANTIZATION_METHODS = {\n"
    '    "fp8": Fp8Config,\n',
    "CPU_QUANTIZATION_METHODS = {\n"
    '    "fp8": Fp8Config,\n'
    '    "mxfp4": Mxfp4Config,\n',
)

if src == original:
    print("ERROR: no patch site matched. The file may have changed shape.", file=sys.stderr)
    sys.exit(1)

INIT.write_text(src)
print(f"Patched {INIT}")
