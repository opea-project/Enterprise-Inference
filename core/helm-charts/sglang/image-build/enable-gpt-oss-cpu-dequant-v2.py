"""Replace `_process_weights_for_cpu` in Mxfp4MoEMethod with a self-contained,
debuggable MXFP4 -> bf16 dequant.

After fix4-fix6 the gpt-oss-20b pipeline ran end-to-end and returned 200, but
the generated tokens were random vocabulary — the classic signature of
corrupted weights producing essentially random logits. The dequant math in
`MXFP4QuantizeUtil.dequantize` is OCP-spec-compliant, but there is one
implementation choice that differs in the wild: the **nibble packing order**
inside each uint8.

`MXFP4QuantizeUtil` uses:
    even index <- low 4 bits
    odd index  <- high 4 bits

while triton_kernels / NVIDIA's reference uses:
    even index <- high 4 bits
    odd index  <- low 4 bits

If gpt-oss is stored with the latter convention, our previous dequant
swapped every (even, odd) pair, producing structurally garbage weights.

This patch:

1. Inlines a self-contained `_dequant_mxfp4_cpu` function that:
   - Has explicit control over nibble order via `MXFP4_NIBBLE_ORDER` env var
     ("low_first" or "high_first"; default "high_first" — the triton_kernels
     convention which is what gpt-oss is stored as)
   - Logs basic stats (shape, dtype, min/max/mean abs) so we can verify the
     dequantized weights look sane
2. Calls it from `_process_weights_for_cpu` instead of MXFP4QuantizeUtil.

The function is conservative: it only changes the nibble extraction logic;
sign/magnitude/E2M1/scale math is identical to MXFP4QuantizeUtil.
"""

import sys
from pathlib import Path

F = Path(
    "/opt/.venv/lib/python3.12/site-packages/sglang/srt/layers/quantization/mxfp4.py"
)
src = F.read_text()
original = src

# Replace the body of _process_weights_for_cpu and add a helper.
# Anchor: the full helper as written by fix4's enable-gpt-oss-cpu-moe.py.
old_helper = (
    "    def _process_weights_for_cpu(self, layer):\n"
    "        \"\"\"Dequantize MXFP4 -> bf16 then AMX-pack for fused_experts_cpu.\n"
    "\n"
    "        Layer params after this call:\n"
    "          - layer.w13_weight: bf16, AMX-packed, shape (E, 2*N, K)\n"
    "          - layer.w2_weight:  bf16, AMX-packed, shape (E, K, N)\n"
    "          - layer.w13_weight_scale / w2_weight_scale: deleted\n"
    "        \"\"\"\n"
    "        import torch\n"
    "        from torch.nn import Parameter\n"
    "        from sglang.srt.layers.quantization.mxfp4_tensor import (\n"
    "            MXFP4QuantizeUtil,\n"
    "        )\n"
    "        from sglang.srt.layers.amx_utils import (\n"
    "            _amx_process_weight_after_loading,\n"
    "        )\n"
    "\n"
    "        def _dequant(weight, scale):\n"
    "            return MXFP4QuantizeUtil.dequantize(\n"
    "                quantized_data=weight,\n"
    "                dtype=torch.bfloat16,\n"
    "                scale=scale,\n"
    "                block_sizes=[32],\n"
    "            )\n"
    "\n"
    "        w13_bf16 = _dequant(layer.w13_weight, layer.w13_weight_scale)\n"
    "        w2_bf16 = _dequant(layer.w2_weight, layer.w2_weight_scale)\n"
    "\n"
    "        del layer.w13_weight\n"
    "        del layer.w2_weight\n"
    "        del layer.w13_weight_scale\n"
    "        del layer.w2_weight_scale\n"
    "        layer.w13_weight = Parameter(w13_bf16.contiguous(), requires_grad=False)\n"
    "        layer.w2_weight = Parameter(w2_bf16.contiguous(), requires_grad=False)\n"
    "\n"
    "        _amx_process_weight_after_loading(layer, [\"w13_weight\", \"w2_weight\"])\n"
)

new_helper = '''    def _process_weights_for_cpu(self, layer):
        """Dequantize MXFP4 -> bf16 then AMX-pack for fused_experts_cpu.

        Layer params after this call:
          - layer.w13_weight: bf16, AMX-packed, shape (E, 2*N, K)
          - layer.w2_weight:  bf16, AMX-packed, shape (E, K, N)
          - layer.w13_weight_scale / w2_weight_scale: deleted
        """
        import os
        import torch
        from torch.nn import Parameter
        from sglang.srt.layers.amx_utils import (
            _amx_process_weight_after_loading,
        )

        nibble_order = os.environ.get("MXFP4_NIBBLE_ORDER", "high_first").lower()

        # E2M1 lookup table (OCP MXFP4 spec)
        _E2M1 = torch.tensor(
            [0.0, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0],
            dtype=torch.float32,
        )

        def _dequant_mxfp4_cpu(weight_packed, scale_e8m0):
            """Dequantize MXFP4 packed uint8 weights to bf16.

            weight_packed: (..., K_packed) uint8, where K_packed = K / 2
                           (2 mxfp4 values per uint8 byte)
            scale_e8m0:    (..., K_blocks) uint8, where K_blocks = K / 32
                           (one E8M0 scale per 32 elements)

            Returns: (..., K) bf16
            """
            assert weight_packed.dtype == torch.uint8
            assert scale_e8m0.dtype == torch.uint8
            device = weight_packed.device
            e2m1 = _E2M1.to(device)

            # Extract the two nibbles per byte
            low_nibble = (weight_packed & 0x0F)              # bits 3:0
            high_nibble = (weight_packed >> 4) & 0x0F        # bits 7:4

            # Interleave to undo the packing
            shape = list(weight_packed.shape)
            shape[-1] = shape[-1] * 2
            unfused = torch.empty(shape, dtype=torch.uint8, device=device)
            if nibble_order == "low_first":
                # MXFP4QuantizeUtil convention: even <- low, odd <- high
                unfused[..., 0::2] = low_nibble
                unfused[..., 1::2] = high_nibble
            else:
                # triton_kernels / NVIDIA reference convention:
                # even <- high, odd <- low
                unfused[..., 0::2] = high_nibble
                unfused[..., 1::2] = low_nibble

            # E2M1: bit 3 = sign, bits 2:0 = magnitude index
            sign = 1.0 - 2.0 * ((unfused >> 3) & 1).float()
            magnitude_idx = (unfused & 0x07).long()
            values = e2m1[magnitude_idx] * sign

            # Apply E8M0 scale: each scale covers 32 consecutive elements
            *batch_dims, K = values.shape
            K_blocks = scale_e8m0.shape[-1]
            if K != K_blocks * 32:
                raise ValueError(
                    f"dequant shape mismatch: dequantized K={K}, "
                    f"K_blocks*32={K_blocks*32} from scale shape {tuple(scale_e8m0.shape)}"
                )
            values = values.view(*batch_dims, K_blocks, 32)
            scale_f = torch.exp2(scale_e8m0.float() - 127.0).unsqueeze(-1)
            out = (values * scale_f).view(*batch_dims, K).to(torch.bfloat16)
            return out

        import logging as _logging
        _log = _logging.getLogger(__name__)

        w13_bf16 = _dequant_mxfp4_cpu(layer.w13_weight, layer.w13_weight_scale)
        w2_bf16 = _dequant_mxfp4_cpu(layer.w2_weight, layer.w2_weight_scale)

        # One-line sanity log so we can see if the dequantized values look sane.
        # Healthy bf16 model weights typically have |w| in [1e-3, ~1.0]; gibberish-
        # producing weights often show abs-mean either suspiciously huge or near 0.
        _log.info(
            "[mxfp4-cpu-dequant] nibble_order=%s w13: shape=%s abs(min=%.4g, max=%.4g, mean=%.4g) "
            "w2: shape=%s abs(min=%.4g, max=%.4g, mean=%.4g)",
            nibble_order,
            tuple(w13_bf16.shape),
            float(w13_bf16.abs().min()),
            float(w13_bf16.abs().max()),
            float(w13_bf16.abs().float().mean()),
            tuple(w2_bf16.shape),
            float(w2_bf16.abs().min()),
            float(w2_bf16.abs().max()),
            float(w2_bf16.abs().float().mean()),
        )

        del layer.w13_weight
        del layer.w2_weight
        del layer.w13_weight_scale
        del layer.w2_weight_scale
        layer.w13_weight = Parameter(w13_bf16.contiguous(), requires_grad=False)
        layer.w2_weight = Parameter(w2_bf16.contiguous(), requires_grad=False)

        _amx_process_weight_after_loading(layer, ["w13_weight", "w2_weight"])
'''

if old_helper not in src:
    print("ERROR: old _process_weights_for_cpu helper not found "
          "(was fix4 applied?)", file=sys.stderr)
    sys.exit(1)
src = src.replace(old_helper, new_helper)

if src == original:
    print("ERROR: nothing was patched", file=sys.stderr)
    sys.exit(1)

F.write_text(src)
print(f"Patched {F}")
