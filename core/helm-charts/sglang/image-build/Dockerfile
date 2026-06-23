# Custom sglang xeon image with two fixes layered onto the upstream image:
#   1. sgl-kernel rebuilt with AVX-512-BF16 / AMX flags so bf16 inference
#      doesn't crash on the unimplemented tinygemm_kernel_nn stub.
#   2. mxfp4 quantization registered for CPU device so openai/gpt-oss-*
#      can be loaded and served (it dequantizes to bf16 at weight-load
#      time via gpt_oss._load_weights_mxfp4 → fp8_utils.dequant_mxfp4,
#      which is pure PyTorch and CPU-friendly).
#
# Tested on Intel Xeon 6972P (Granite Rapids).
# Build: docker build -t enterprise-inference/sglang:v0.5.12-xeon-fix1 .

FROM lmsysorg/sglang:v0.5.12-xeon

# ---- 1) Rebuild sgl-kernel with proper CPU compile flags ----
# The upstream image's published .so is compiled without -mavx512bf16, so
# the at::BFloat16 specialization of tinygemm_kernel_nn is effectively missing
# and falls through to a TORCH_CHECK(false, "scalar path not implemented!").
# We rebuild it from the in-image source with the right flags.
ENV CMAKE_BF16_FLAGS="-march=sapphirerapids -mtune=native -mavx512f -mavx512bw -mavx512vl -mavx512dq -mavx512bf16 -mamx-bf16 -mamx-int8 -mamx-tile -O3 -DNDEBUG"

RUN bash -lc '\
    set -ex; \
    source /opt/.venv/bin/activate; \
    UV=/root/.local/bin/uv; \
    "$UV" pip install --no-deps scikit-build-core ninja cmake setuptools wheel pyproject_metadata pathspec; \
    cd /sgl-workspace/sglang/sgl-kernel; \
    cp pyproject_cpu.toml pyproject.toml; \
    export CMAKE_CXX_FLAGS="$CMAKE_BF16_FLAGS"; \
    export CMAKE_C_FLAGS="$CMAKE_BF16_FLAGS"; \
    export CMAKE_BUILD_PARALLEL_LEVEL=64; \
    export SKBUILD_CMAKE_ARGS="-DCMAKE_CXX_FLAGS=$CMAKE_BF16_FLAGS;-DCMAKE_C_FLAGS=$CMAKE_BF16_FLAGS;-DCMAKE_BUILD_TYPE=Release"; \
    "$UV" pip install --force-reinstall --no-deps --no-build-isolation -v . 2>&1 | tail -20; \
    SO=$(find /opt/.venv -name "common_ops*.so" | head -1); \
    echo "=== rebuilt $SO ==="; \
    ls -la "$SO"; \
    BF16=$(objdump -d "$SO" 2>/dev/null | grep -cE "vdpbf16ps|vfmadd.*bh" || true); \
    echo "AVX-512 BF16 instructions in rebuilt .so: $BF16"; \
    if [ "$BF16" -lt 100 ]; then echo "ERROR: rebuild did not emit BF16 instructions"; exit 1; fi \
'

# ---- 2) Patch quantization registration so mxfp4 works on CPU ----
# The upstream code gates "mxfp4" behind is_cuda() or is_hip(); on CPU it
# never registers, and any model with quant_method=mxfp4 fails at config
# validation. The CPU dequant + bf16 forward path for gpt_oss already exists
# in the codebase (fp8_utils.dequant_mxfp4 + gpt_oss._load_weights_mxfp4) —
# the registration gate is the only missing piece.
COPY enable-mxfp4-cpu.py /tmp/enable-mxfp4-cpu.py
RUN /opt/.venv/bin/python3 /tmp/enable-mxfp4-cpu.py && rm /tmp/enable-mxfp4-cpu.py

# Sanity check: after the patch, importing should not error and mxfp4 should
# be in QUANTIZATION_METHODS when SGLANG_USE_CPU_ENGINE=1.
RUN SGLANG_USE_CPU_ENGINE=1 /opt/.venv/bin/python3 -c "\
from sglang.srt.layers.quantization import QUANTIZATION_METHODS, CPU_QUANTIZATION_METHODS; \
assert 'mxfp4' in QUANTIZATION_METHODS, 'mxfp4 not in QUANTIZATION_METHODS'; \
assert 'mxfp4' in CPU_QUANTIZATION_METHODS, 'mxfp4 not in CPU_QUANTIZATION_METHODS'; \
print('OK: mxfp4 registered for CPU')"

# ---- 3) Allow CPU attention backends for GptOssForCausalLM ----
# server_args.py hardcodes an allowlist of attention backends for gpt-oss
# that omits CPU options. Patch it to default to intel_amx on CPU and to
# accept intel_amx / torch_native as valid backends.
COPY enable-gpt-oss-cpu.py /tmp/enable-gpt-oss-cpu.py
RUN /opt/.venv/bin/python3 /tmp/enable-gpt-oss-cpu.py && rm /tmp/enable-gpt-oss-cpu.py

# ---- 4) Make gpt_oss.py weight loaders CPU-safe ----
# The model file hardcodes `.cuda()` and `torch.cuda.empty_cache/synchronize`
# in its MXFP4 weight loader and dequant helper, which abort on CPU-only torch.
# Guard each call with `if torch.cuda.is_available():`.
COPY enable-gpt-oss-cpu-loaders.py /tmp/enable-gpt-oss-cpu-loaders.py
RUN /opt/.venv/bin/python3 /tmp/enable-gpt-oss-cpu-loaders.py && rm /tmp/enable-gpt-oss-cpu-loaders.py

# ---- 5) Wire a CPU forward path into Mxfp4MoEMethod ----
# Mxfp4MoEMethod ships only GPU branches (marlin/cutlass/flashinfer/aiter/
# triton_kernels). This patch adds a CPU branch that dequantizes MXFP4 -> bf16
# at weight-loading time and then routes the MoE forward through
# `torch.ops.sgl_kernel.fused_experts_cpu` (the same kernel the unquantized
# bf16 MoE method already uses in unquant.py:forward_cpu).
COPY enable-gpt-oss-cpu-moe.py /tmp/enable-gpt-oss-cpu-moe.py
RUN /opt/.venv/bin/python3 /tmp/enable-gpt-oss-cpu-moe.py && rm /tmp/enable-gpt-oss-cpu-moe.py

# ---- 6) Add sinks-attention support to torch_native_backend ----
# gpt-oss uses sink attention (a learnable per-head scalar added to the softmax
# denominator). No CPU backend in sglang supports the `sinks` kwarg today.
# This patch adds it to torch_native_backend with the exact math sglang's own
# triton kernel uses (extend_attention.py lines 535-537).
COPY enable-cpu-sinks-attention.py /tmp/enable-cpu-sinks-attention.py
RUN /opt/.venv/bin/python3 /tmp/enable-cpu-sinks-attention.py && rm /tmp/enable-cpu-sinks-attention.py

# ---- 7) Replace _process_weights_for_cpu with self-contained dequant ----
# fix6 produced /generate 200 but with random-vocab output — classic signature
# of corrupted weights. Hypothesis: MXFP4 nibble packing order in gpt-oss's
# storage doesn't match what MXFP4QuantizeUtil uses. This patch swaps the
# dequant to a self-contained function with explicit control over nibble
# order via MXFP4_NIBBLE_ORDER env var ("low_first" is correct for gpt-oss
# per the numerical sanity check on layer-0 weight magnitudes).
COPY enable-gpt-oss-cpu-dequant-v2.py /tmp/enable-gpt-oss-cpu-dequant-v2.py
RUN /opt/.venv/bin/python3 /tmp/enable-gpt-oss-cpu-dequant-v2.py && rm /tmp/enable-gpt-oss-cpu-dequant-v2.py

# ---- 8) Route Mxfp4MoEMethod.forward_cpu through moe_forward_native ----
# After fix7 dequant produces sane weights, but fused_experts_cpu uses plain
# silu(gate)*up with no biases, no alpha, no clamp — wrong activation for
# gpt-oss → gibberish output. moe_forward_native is sglang's pure-Python MoE
# reference that already handles gpt-oss-specific swiglu (alpha + clamp +
# interleaved gate/up + (up+1)) and W13/W2 biases. Also strips the AMX-pack
# call because moe_forward_native uses F.linear on un-packed bf16 weights.
COPY enable-gpt-oss-cpu-moe-v2.py /tmp/enable-gpt-oss-cpu-moe-v2.py
RUN /opt/.venv/bin/python3 /tmp/enable-gpt-oss-cpu-moe-v2.py && rm /tmp/enable-gpt-oss-cpu-moe-v2.py

# ---- 9) DEBUG: allow --dtype float32 with mxfp4 (for precision-drift A/B) ----
# server_args.py hard-forces dtype=bfloat16 for mxfp4 models. Gate that behind
# ALLOW_FP32_MXFP4=1 so we can A/B bf16 vs fp32 for Phase 2 numerical
# investigation. Not for production — fp32 is 2x memory and significantly
# slower than the bf16 path.
COPY enable-fp32-override-debug.py /tmp/enable-fp32-override-debug.py
RUN /opt/.venv/bin/python3 /tmp/enable-fp32-override-debug.py && rm /tmp/enable-fp32-override-debug.py

# ---- 10) DEBUG: make MXFP4-CPU dequant output dtype env-controlled ----
# fix7's _process_weights_for_cpu hardcoded bf16 output. With fix9-debug
# allowing --dtype half, the dequant output dtype needs to match the rest
# of the model's compute dtype. Drive it from MXFP4_OUT_DTYPE env var.
COPY enable-dequant-dtype-debug.py /tmp/enable-dequant-dtype-debug.py
RUN /opt/.venv/bin/python3 /tmp/enable-dequant-dtype-debug.py && rm /tmp/enable-dequant-dtype-debug.py

# ---- 11) DEBUG: fp32 promotion inside moe_forward_native per-expert loop ----
# Phase 2 confirmed bf16 intermediate precision is a contributor to long-form
# drift (fp16 shifted the drift point ~30%). Option 1 in REMAINING_WORK.md:
# keep layer weights/KV in their native dtype, but compute the per-expert
# forward in fp32 — both F.linear matmuls, biases, and the swiglu chain —
# casting back only at the expert output boundary. Gated behind
# FP32_PROMOTE_MOE=1 so the image is safe to run with the flag off.
COPY enable-fp32-moe-promotion-debug.py /tmp/enable-fp32-moe-promotion-debug.py
RUN /opt/.venv/bin/python3 /tmp/enable-fp32-moe-promotion-debug.py && rm /tmp/enable-fp32-moe-promotion-debug.py

# ---- 12) DEBUG: allow --kv-cache-dtype float32 end-to-end ----
# Phase 2 Option 2 — add float32 to the argparse choices, map it through
# configure_kv_cache_dtype, and fix torch_native_backend's dtype-mismatch
# handler so it upcasts Q to fp32 instead of silently downcasting K/V back
# to bf16. With anything other than float32/fp32 selected, all three sites
# are byte-identical to upstream.
COPY enable-fp32-kv-cache-debug.py /tmp/enable-fp32-kv-cache-debug.py
RUN /opt/.venv/bin/python3 /tmp/enable-fp32-kv-cache-debug.py && rm /tmp/enable-fp32-kv-cache-debug.py

# Mirror the upstream env vars so behavior is unchanged
ENV SGLANG_USE_CPU_ENGINE=1
ENV LD_PRELOAD=/usr/lib/x86_64-linux-gnu/libtcmalloc.so.4:/usr/lib/x86_64-linux-gnu/libtbbmalloc.so:/opt/.venv/lib/libiomp5.so

WORKDIR /sgl-workspace/sglang
