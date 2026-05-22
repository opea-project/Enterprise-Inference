"""Patch sglang's server_args.py so GptOssForCausalLM accepts CPU attention backends.

The upstream gate at the GptOssForCausalLM branch:
  1. Has no `is_cpu()` case for default backend selection — falls to "triton",
     which has no CPU implementation.
  2. The `supported_backends` allowlist omits "intel_amx" and "torch_native",
     even though both are valid CPU attention backends registered via
     attention_registry.py.

We extend both: pick `intel_amx` as the default for the CPU engine, and add
intel_amx + torch_native to the allowlist so users can choose either.
"""

import sys
from pathlib import Path

SA = Path(
    "/opt/.venv/lib/python3.12/site-packages/sglang/srt/server_args.py"
)
src = SA.read_text()
original = src

# 1) Inject is_cpu() branch into the default attention backend selector for
#    GptOssForCausalLM. We sit between the existing `elif is_hip(): aiter`
#    and the final `else: triton` so CPU users get intel_amx.
needle = (
    '                elif is_hip():\n'
    '                    self.attention_backend = "aiter"\n'
    '                else:\n'
    '                    self.attention_backend = "triton"\n'
)
replacement = (
    '                elif is_hip():\n'
    '                    self.attention_backend = "aiter"\n'
    '                elif os.getenv("SGLANG_USE_CPU_ENGINE", "0") == "1":\n'
    '                    self.attention_backend = "intel_amx"\n'
    '                else:\n'
    '                    self.attention_backend = "triton"\n'
)
if needle not in src:
    print("ERROR: default attention backend selector for GptOss not found", file=sys.stderr)
    sys.exit(1)
src = src.replace(needle, replacement)

# 2) Extend supported_backends to include CPU options.
needle2 = (
    '            supported_backends = [\n'
    '                "triton",\n'
    '                "trtllm_mha",\n'
    '                "fa3",\n'
    '                "fa4",\n'
    '                "ascend",\n'
    '                "intel_xpu",\n'
    '                "aiter",\n'
    '            ]\n'
)
replacement2 = (
    '            supported_backends = [\n'
    '                "triton",\n'
    '                "trtllm_mha",\n'
    '                "fa3",\n'
    '                "fa4",\n'
    '                "ascend",\n'
    '                "intel_xpu",\n'
    '                "aiter",\n'
    '                "intel_amx",\n'
    '                "torch_native",\n'
    '            ]\n'
)
if needle2 not in src:
    print("ERROR: supported_backends list for GptOss not found", file=sys.stderr)
    sys.exit(1)
src = src.replace(needle2, replacement2)

# 3) Ensure `os` is imported (cheap idempotent check)
if "\nimport os" not in src and not src.startswith("import os"):
    src = "import os\n" + src

if src == original:
    print("ERROR: nothing was patched", file=sys.stderr)
    sys.exit(1)

SA.write_text(src)
print(f"Patched {SA}")
