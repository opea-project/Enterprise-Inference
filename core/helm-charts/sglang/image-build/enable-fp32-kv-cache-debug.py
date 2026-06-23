"""Debug-only patch: allow ``--kv-cache-dtype float32`` end-to-end.

Phase 2 Option 2 hypothesis is that bf16 KV cache write/read truncates
attention K/V state every token, and the per-step error compounds with
sequence length — matching the symptom that later tokens have worse
output. sglang's flag space only exposes ``auto / bf16 / bfloat16 /
fp8_e5m2 / fp8_e4m3 / fp4_e2m1``; ``float32`` was never an option.

This patch makes three surgical changes so fp32 KV flows end-to-end:

1. ``server_args.py``: add ``float32`` (with ``fp32`` as an alias) to
   the ``--kv-cache-dtype`` ``choices`` list.

2. ``model_runner.py::configure_kv_cache_dtype``: map both strings to
   ``torch.float32`` so the allocator allocates fp32 KV tensors.

3. ``torch_native_backend.py``: fix the dtype-mismatch branch in both
   extend and decode SDPA call sites. Today it always casts K/V to
   ``query.dtype``, which would silently downcast our fp32 KV to bf16
   for the attention math — defeating the whole point. With this
   patch, when K/V have higher precision than Q we upcast Q to match,
   keeping the SDPA matmuls in fp32 and downcasting the output back to
   the original query dtype at the boundary.

Gated by the choice of ``--kv-cache-dtype`` at runtime; with anything
other than ``float32``/``fp32`` selected, all three sites are
byte-identical to upstream.

Diagnostic build only.
"""

import sys
from pathlib import Path

# ---- 1) server_args.py: add float32 to argparse choices ------------------
F1 = Path(
    "/opt/.venv/lib/python3.12/site-packages/sglang/srt/server_args.py"
)
src1 = F1.read_text()
orig1 = src1

old1 = (
    '            choices=["auto", "fp8_e5m2", "fp8_e4m3", "bf16", "bfloat16", "fp4_e2m1"],\n'
)
new1 = (
    '            choices=["auto", "fp8_e5m2", "fp8_e4m3", "bf16", "bfloat16", "fp4_e2m1", "float32", "fp32"],\n'
)
if old1 not in src1:
    print("ERROR: kv-cache-dtype choices anchor not found in server_args.py", file=sys.stderr)
    sys.exit(1)
src1 = src1.replace(old1, new1)


# ---- 2) model_runner.py: extend configure_kv_cache_dtype ------------------
F2 = Path(
    "/opt/.venv/lib/python3.12/site-packages/sglang/srt/model_executor/model_runner.py"
)
src2 = F2.read_text()
orig2 = src2

# Insert a new elif branch just before the existing "elif fp4_e2m1" handler.
old2 = (
    '        elif self.server_args.kv_cache_dtype in ("bf16", "bfloat16"):\n'
    '            self.kv_cache_dtype = torch.bfloat16\n'
)
new2 = (
    '        elif self.server_args.kv_cache_dtype in ("bf16", "bfloat16"):\n'
    '            self.kv_cache_dtype = torch.bfloat16\n'
    '        elif self.server_args.kv_cache_dtype in ("float32", "fp32"):\n'
    '            # fix11-debug: fp32 KV cache for Phase 2 Option 2 long-form\n'
    '            # precision A/B. ~2x KV memory; torch_native_backend will\n'
    '            # upcast Q to fp32 at SDPA time (see patch (3) below).\n'
    '            self.kv_cache_dtype = torch.float32\n'
)
if old2 not in src2:
    print("ERROR: configure_kv_cache_dtype anchor not found in model_runner.py", file=sys.stderr)
    sys.exit(1)
src2 = src2.replace(old2, new2)


# ---- 3) torch_native_backend.py: upcast Q when KV is higher precision -----
F3 = Path(
    "/opt/.venv/lib/python3.12/site-packages/sglang/srt/layers/attention/torch_native_backend.py"
)
src3 = F3.read_text()
orig3 = src3

# Two identical mismatch-handler blocks (extend + decode). Replace both with
# a version that picks the higher-precision dtype across (Q, K, V) and
# upcasts the others to match.
old3 = (
    '            if not (per_req_query.dtype == per_req_key.dtype == per_req_value.dtype):\n'
    '                # _sdpa_with_sinks() expects query, key, and value to have the same dtype\n'
    '                per_req_key = per_req_key.to(per_req_query.dtype)\n'
    '                per_req_value = per_req_value.to(per_req_query.dtype)\n'
)
new3 = (
    '            if not (per_req_query.dtype == per_req_key.dtype == per_req_value.dtype):\n'
    '                # fix11-debug: pick the highest-precision dtype across Q/K/V and\n'
    '                # promote the others to match, instead of unconditionally\n'
    '                # downcasting K/V to query.dtype. Required so fp32 KV cache\n'
    '                # actually produces fp32 SDPA math; harmless otherwise.\n'
    '                import torch as _torch\n'
    '                _rank = {\n'
    '                    _torch.float32: 3,\n'
    '                    _torch.float16: 2,\n'
    '                    _torch.bfloat16: 2,\n'
    '                }\n'
    '                _best = max(\n'
    '                    (per_req_query.dtype, per_req_key.dtype, per_req_value.dtype),\n'
    '                    key=lambda d: _rank.get(d, 0),\n'
    '                )\n'
    '                per_req_query = per_req_query.to(_best)\n'
    '                per_req_query_redudant = (\n'
    '                    per_req_query_redudant.to(_best)\n'
    '                    if "per_req_query_redudant" in dir() else None\n'
    '                )\n'
    '                per_req_key = per_req_key.to(_best)\n'
    '                per_req_value = per_req_value.to(_best)\n'
)
count = src3.count(old3)
if count != 2:
    print(
        f"ERROR: expected exactly 2 SDPA-mismatch handler sites in torch_native_backend.py, found {count}",
        file=sys.stderr,
    )
    sys.exit(1)
src3 = src3.replace(old3, new3)


# ---- write all three back ------------------------------------------------
if src1 == orig1 or src2 == orig2 or src3 == orig3:
    print("ERROR: at least one of the three patches was a no-op", file=sys.stderr)
    sys.exit(1)

F1.write_text(src1)
print(f"Patched {F1}")
F2.write_text(src2)
print(f"Patched {F2}")
F3.write_text(src3)
print(f"Patched {F3}")
