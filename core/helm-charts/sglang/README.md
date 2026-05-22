# SGLang Helm Chart (Xeon CPU build)

Deploys an [SGLang](https://github.com/sgl-project/sglang) inference server
using the `lmsysorg/sglang:v0.5.11-xeon` image on an Intel Xeon (AMX) CPU
node. Follows the same standalone pattern as `core/helm-charts/ovms` — it
is **not** wired into the Ansible playbooks. Deploy with `helm install`.

## Supported models / quantizations

This image's source explicitly limits CPU quantization to a small set
(`sglang/srt/layers/quantization/__init__.py`, `CPU_QUANTIZATION_METHODS`):

| Quantization        | Works on this image? |
| ------------------- | -------------------- |
| `fp8`               | yes                  |
| `w8a8_int8`         | yes                  |
| `compressed-tensors`| yes                  |
| `awq`               | yes (`AWQCPUConfig`) |
| `gptq`              | yes (`CPUGPTQConfig`)|
| **`mxfp4`**         | **no — GPU only**    |
| `modelopt_fp4`      | no                   |
| anything else       | no                   |

Models that work out of the box on Xeon CPU:

- `Qwen/Qwen3-8B` (bf16, default) — small, fast, no quantization gate
- `Qwen/Qwen2.5-7B-Instruct` / `Qwen/Qwen2.5-14B-Instruct`
- `meta-llama/Llama-3.1-8B-Instruct` (gated, needs HF token)
- `deepseek-ai/DeepSeek-V3.1-Terminus` channel-quantized variants
  (e.g. `IntervitensInc/DeepSeek-V3.1-Terminus-Channel-int8` with
  `--set server.quantization=w8a8_int8`)

### gpt-oss-20b / gpt-oss-120b

`openai/gpt-oss-*` is shipped natively in **MXFP4**, which is not
implemented for CPU in any sglang build to date — the `mxfp4` entry in
`BASE_QUANTIZATION_METHODS` is gated behind `is_cuda() or is_hip()`. This
chart will exit at startup with
`ValueError: Unknown quantization method: mxfp4` if you point it at gpt-oss.

To serve gpt-oss-20b on Xeon CPU, use a different runtime — llama.cpp,
Ollama, vLLM CPU, or ipex-llm — with a GGUF variant (e.g.
`ggml-org/gpt-oss-20b-GGUF`, `unsloth/gpt-oss-20b-GGUF`,
`bartowski/openai_gpt-oss-20b-GGUF`). Not this chart.

To serve gpt-oss-20b via sglang, use a GPU image (e.g.
`lmsysorg/sglang:v0.5.11-cuda`) on a CUDA host. The chart can be reused —
just override `image.tag` and `server.device=cuda`.

## Prerequisites

- Kubernetes 1.24+
- Helm 3+
- For the gated-model recipes: HuggingFace token with read scope

## Quick start (smoke test, no auth)

```bash
helm upgrade --install qwen3-8b core/helm-charts/sglang \
  --set apisixRoute.enabled=false \
  --set ingress.enabled=false \
  --set oidc.enabled=false

kubectl get pods -l app.kubernetes.io/instance=qwen3-8b -w
kubectl port-forward svc/qwen3-8b-sglang 30000:30000 &

curl http://localhost:30000/v1/models
curl http://localhost:30000/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"qwen3-8b","messages":[{"role":"user","content":"Say hi."}]}'
```

The default model is `Qwen/Qwen3-8B`. To swap models, override
`modelSource` and `modelName`:

```bash
helm upgrade --install llama-3-1-8b core/helm-charts/sglang \
  --set modelSource="meta-llama/Llama-3.1-8B-Instruct" \
  --set modelName="llama-3-1-8b" \
  --set huggingface.token=$HF_TOKEN
```

## Full deploy (with Keycloak/APISIX/Ingress)

The chart's default values turn on the same OIDC+APISIX+Ingress wiring
that the OVMS chart uses, so a fully-provisioned Enterprise-Inference
cluster will route to this server at `https://<cluster_url>/<modelName>-sglang/*`.
For a stand-alone cluster, override the auth stack values per the smoke
test above.

## Tuning for Xeon

- `cpuEngine.ompThreadsBind`: pin SGLang's OMP threads per tp rank. For a
  2-rank tp on a 64-core node:
  `--set server.tpSize=2 --set cpuEngine.ompThreadsBind="0-31|32-63"`.
- `server.enableTorchCompile=true`: large speedup, longer cold start.
  Pair with `server.torchCompileMaxBs` (default 4).
- `server.quantization=w8a8_int8` with an int8-quantized checkpoint is
  typically the sweet spot for throughput on Xeon AMX.
- Memory is the most common bottleneck. Set `resources.limits.memory`
  to weights + KV cache + ~10Gi headroom.

## Known upstream issue

As of 2026-05, both `lmsysorg/sglang:v0.5.11-xeon` and `v0.5.12-xeon`
crash on the first forward pass with a `c10::Error` inside
`logits_processor._compute_lm_head`. We reproduced this with:

- Qwen/Qwen2.5-7B-Instruct (`Qwen2ForCausalLM`)
- Qwen/Qwen3-8B (`Qwen3ForCausalLM`)
- `attention_backend=intel_amx` (default) and `=torch_native`
- with and without `LD_PRELOAD` baked in by the image

The model loads, KV cache allocates, uvicorn serves `/model_info` 200 OK,
then the scheduler subprocess aborts during sglang's auto warmup-`/generate`.
That points at the CPU matmul kernel in the image rather than anything
the chart configures. Until the upstream image fixes it, this chart
cannot end-to-end-serve a request on Xeon.

The chart is otherwise validated end-to-end:
- pod schedules, image pulls, PVC binds, Service routes
- `SGLANG_USE_CPU_ENGINE=1` → `attention_backend='intel_amx'` selected
- `--max-total-tokens` prevents the host-RAM-fraction OOM (sglang reads
  host memory, not cgroup limits)
- weights and KV cache allocate cleanly within pod limits
- uvicorn starts and serves `/model_info`

When the upstream bug is fixed (track sgl-project/sglang for AMX matmul
fixes on the xeon Dockerfile), no chart changes should be required.

## References

- [sglang CPU server docs](https://docs.sglang.io/platforms/cpu_server.html)
- `docker/xeon.Dockerfile` in the sglang repo — the canonical build recipe
- For gpt-oss-on-CPU: [llama.cpp guide](https://github.com/ggml-org/llama.cpp/discussions/15396),
  [Ollama gpt-oss:20b](https://ollama.com/library/gpt-oss:20b)
