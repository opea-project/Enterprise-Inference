"""Add a CPU forward path to sglang.srt.layers.quantization.mxfp4.Mxfp4MoEMethod.

Upstream `Mxfp4MoEMethod` only ships GPU branches (Marlin, FlashInfer cutlass
SM90, FlashInfer TRT-LLM SM100, AMD aiter, NVIDIA triton_kernels). On CPU,
both its `process_weights_after_loading` and `apply` raise (the former tries
to `import triton_kernels`; the latter has no CPU branch at all).

This patch:

1. Adds a CPU branch at the top of `process_weights_after_loading` that:
     a. Dequantizes the MXFP4-packed `w13_weight` / `w2_weight` to bf16
        using the pure-PyTorch `MXFP4QuantizeUtil.dequantize` helper that
        already ships in `mxfp4_tensor.py`.
     b. Calls `_amx_process_weight_after_loading` (the same helper that the
        bf16 unquantized MoE method uses in `unquant.py:process_weights_after_loading`)
        to AMX-pack the bf16 weights for `fused_experts_cpu`.
     c. Returns early so none of the CUDA-only branches run.

2. Adds a `forward_cpu` method that mirrors the unquantized bf16 MoE method's
   CPU forward path (`unquant.py:forward_cpu`) verbatim — apply_topk_weights_cpu,
   then `torch.ops.sgl_kernel.fused_experts_cpu(..., CPUQuantMethod.UNQUANT, ...)`.

After this patch the weights are stored as bf16 inside the layer (the MXFP4
packed storage is replaced), so the existing CPU `fused_experts_cpu` AMX
kernel handles them like any other bf16 MoE.
"""

import sys
from pathlib import Path

F = Path(
    "/opt/.venv/lib/python3.12/site-packages/sglang/srt/layers/quantization/mxfp4.py"
)
src = F.read_text()
original = src

# ----- 1. Insert CPU branch + helper into Mxfp4MoEMethod.process_weights_after_loading -----
#
# Anchor on the first line of the existing method body. We prepend a CPU
# branch that does the dequant + AMX pack, then returns. Existing logic
# (marlin / cutlass / flashinfer / triton_kernels / `torch.cuda.empty_cache`)
# is untouched on GPU.

needle_pwal = (
    "    def process_weights_after_loading(self, layer):\n"
    "        if self.use_marlin:\n"
)
replacement_pwal = (
    "    def process_weights_after_loading(self, layer):\n"
    "        # ---- CPU branch added by enable-gpt-oss-cpu-moe.py ----\n"
    "        from sglang.srt.utils import is_cpu, cpu_has_amx_support\n"
    "        if is_cpu() and cpu_has_amx_support():\n"
    "            self._process_weights_for_cpu(layer)\n"
    "            return\n"
    "        # ---- end CPU branch ----\n"
    "        if self.use_marlin:\n"
)
if needle_pwal not in src:
    print("ERROR: process_weights_after_loading anchor not found", file=sys.stderr)
    sys.exit(1)
src = src.replace(needle_pwal, replacement_pwal)

# ----- 2. Add the _process_weights_for_cpu helper + forward_cpu method right
#         BEFORE the `def apply(` of Mxfp4MoEMethod (so they live on the class).
# Anchor on the exact apply signature we read from the running image.
needle_apply = (
    "    def apply(\n"
    "        self,\n"
    "        layer: torch.nn.Module,\n"
    "        dispatch_output: StandardDispatchOutput,\n"
    "    ) -> CombineInput:\n"
)
new_methods = (
    "    # ---- CPU methods added by enable-gpt-oss-cpu-moe.py ----\n"
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
    "\n"
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
    "    # ---- end CPU methods ----\n"
    "\n"
)
replacement_apply = new_methods + needle_apply
if needle_apply not in src:
    print("ERROR: Mxfp4MoEMethod.apply anchor not found", file=sys.stderr)
    sys.exit(1)
src = src.replace(needle_apply, replacement_apply, 1)

# ----- 3. Route Mxfp4MoEMethod.apply() to forward_cpu() on CPU. -----
# FusedMoE.run_moe_core calls apply() directly; our forward_cpu would be
# dead code unless apply() itself delegates. Insert the delegation as the
# very first statement of apply() (after its imports).
needle_apply_body = (
    "    ) -> CombineInput:\n"
    "\n"
    "        from sglang.srt.layers.moe.token_dispatcher import StandardCombineInput\n"
    "        from sglang.srt.layers.moe.topk import TopKOutputChecker\n"
)
replacement_apply_body = (
    "    ) -> CombineInput:\n"
    "\n"
    "        # ---- CPU delegation added by enable-gpt-oss-cpu-moe.py ----\n"
    "        from sglang.srt.utils import is_cpu, cpu_has_amx_support\n"
    "        if is_cpu() and cpu_has_amx_support():\n"
    "            return self.forward_cpu(layer, dispatch_output)\n"
    "        # ---- end CPU delegation ----\n"
    "\n"
    "        from sglang.srt.layers.moe.token_dispatcher import StandardCombineInput\n"
    "        from sglang.srt.layers.moe.topk import TopKOutputChecker\n"
)
if needle_apply_body not in src:
    print("ERROR: apply() body anchor not found", file=sys.stderr)
    sys.exit(1)
src = src.replace(needle_apply_body, replacement_apply_body, 1)

if src == original:
    print("ERROR: nothing changed", file=sys.stderr)
    sys.exit(1)

F.write_text(src)
print(f"Patched {F}")
