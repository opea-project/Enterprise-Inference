# SGLang Helm Chart — gpt-oss-20b on Intel Xeon CPU

## 📋 Overview

Deploys [SGLang](https://github.com/sgl-project/sglang) on a Kubernetes
cluster to serve `openai/gpt-oss-20b` on an Intel Xeon CPU node, including
the OPEA-standard nginx-ingress → APISIX → Keycloak (OIDC) auth chain.

The chart targets a **patched** sglang image (`enterprise-inference/sglang:v0.5.12-xeon-fix11-debug`)
that layers 11 fixes onto `lmsysorg/sglang:v0.5.12-xeon` — without them
the upstream image cannot serve gpt-oss on CPU (MXFP4 quantization is
GPU-gated, sinks attention is not supported on the CPU backends, the
shipped sgl-kernel `.so` is compiled without `-mavx512bf16`, etc.).
The image is built once via a self-contained Dockerfile and imported
directly into k3s containerd — no registry required.

## ✨ Features

- **Single-model gpt-oss-20b** on Xeon CPU through the patched sglang image
- **OPEA-standard auth chain**: TLS at nginx, OIDC bearer validation at APISIX, token issuance by Keycloak
- **No external registry**: image builds locally and imports into k3s containerd
- **OpenAI-compatible API**: `/v1/chat/completions`, `/v1/models`, `/v1/completions`
- **Harmony reasoning + tool-call parsers** pre-wired for gpt-oss
- **Chart-only delivery**: same standalone pattern as `core/helm-charts/ovms`, not yet wired into the Ansible playbooks

## 📦 Prerequisites

- **Operating System**: Ubuntu 22.04+
- **Hardware**: Intel Xeon with AVX-512-BF16 / AMX-BF16 (Sapphire Rapids, Emerald Rapids, Granite Rapids)
- **Memory**: ≥ 64 GiB RAM (gpt-oss-20b uses ~25 GiB dequantized + KV cache)
- **Disk**: ≥ 100 GiB free on the root partition
- **Kubernetes**: 1.24+ (k3s is fine; this chart was validated on single-node k3s)
- **Helm**: 3+
- **NodePorts free on the host**: 30080, 30443 (nginx), 32080 (APISIX)
- **HuggingFace token** (only required for gated repos; `openai/gpt-oss-20b` is public)
- **Sudo access** for the one-shot image build

> **Note:** On a stock OPEA cluster, k3s, nginx-ingress, APISIX, and Keycloak
> are already in place via the project's Ansible playbooks — skip straight to
> 🚀 **Deploy**. The "From-Scratch Bootstrap" appendix at the bottom is only
> for people standing up a fresh single-node box from zero.

## 🛠️ Build the Image

```bash
git clone https://github.com/cld2labs/Enterprise-Inference.git
cd Enterprise-Inference
git checkout cld2labs/sglang-gpt-oss

sudo bash core/helm-charts/sglang/image-build/build-and-import.sh
```

First run takes ~5–10 minutes (installs docker.io if missing, compiles
27 C++ files in `sgl-kernel` with the right BF16 flags, runs 11 Python
patch scripts against sglang's in-image source, and imports the result
into k3s containerd).

Verify:

```bash
sudo k3s ctr images ls | grep enterprise-inference/sglang
# docker.io/enterprise-inference/sglang:v0.5.12-xeon-fix11-debug
```

## 🚀 Deploy

The chart ships with `gpt-oss-20b-values.yaml` as the canonical override
for this model. It pins the image, sets bf16, wires the gpt-oss parsers,
sizes resources for a Xeon node, and enables the full auth chain.

```bash
helm upgrade --install gpt-oss-20b core/helm-charts/sglang \
  -f core/helm-charts/sglang/gpt-oss-20b-values.yaml
```

Wait for the pod (first start downloads ~12 GB of weights, then runs
MXFP4 → bf16 dequant — total ~4–5 minutes):

```bash
kubectl wait --for=condition=ready pod -l app=sglang --timeout=600s
kubectl logs -l app=sglang --tail=5
# expect: INFO: Uvicorn running on http://0.0.0.0:30000
```

## 🎯 Inference

### Smoke Test (no auth, via port-forward)

```bash
kubectl port-forward svc/gpt-oss-20b-sglang 30000:30000 &
sleep 2

curl -sS http://localhost:30000/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "gpt-oss-20b",
    "messages": [{"role":"user","content":"In one sentence, what is deep learning?"}],
    "max_tokens": 150,
    "temperature": 0.3
  }' | python3 -m json.tool
```

### Auth-Routed Call (nginx → APISIX → Keycloak → sglang)

Fetch a token from inside the cluster (so the `iss` claim matches what
APISIX validates against), then call through the ingress:

```bash
TOKEN=$(kubectl run keycloak-tok --rm -i --restart=Never --quiet \
  --image=curlimages/curl:8.10.1 -- \
  sh -c 'curl -sS -X POST http://keycloak.default.svc.cluster.local/realms/master/protocol/openid-connect/token \
    -d "client_id=my-client-id" \
    -d "client_secret=tf29wNR5fZ7edbNmnLSWDEvL7Simx4CR" \
    -d "grant_type=client_credentials"' \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['access_token'])")

curl -sSk https://localhost:30443/gpt-oss-20b-sglang/v1/chat/completions \
  -H "Host: api.example.com" \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "gpt-oss-20b",
    "messages": [{"role":"user","content":"In one sentence, what is deep learning?"}],
    "max_tokens": 150,
    "temperature": 0.3
  }' | python3 -m json.tool
```

### API Endpoints

| Endpoint | Description |
|----------|-------------|
| `/v1/models` | List loaded models |
| `/v1/chat/completions` | OpenAI-compatible chat completions |
| `/v1/completions` | OpenAI-compatible text completions |
| `/health` | Liveness probe |

### Notes on `max_tokens`

gpt-oss uses the **Harmony format**: every response starts in an
"analysis" channel (the model's scratchpad) and only switches to the
"final" channel once it's done thinking. With small budgets the model
spends them all reasoning and emits no user-visible content. Practical
guidance:

| `max_tokens` | What you'll see |
|--------------|-----------------|
| ≤ 100 | Usually `content: null`, reasoning truncated |
| 150 | One short sentence — good for quick demos |
| 300 | Paragraph + small table |
| > 400 | Hits the documented long-form drift (see ⚠️ below) |

The reasoning is preserved in `response.choices[0].message.reasoning_content`
and the visible answer in `response.choices[0].message.content`.

## ⚙️ Configuration

### Key Values

| Key | Default | Description |
|-----|---------|-------------|
| `image.repository` | `enterprise-inference/sglang` | Patched image (override to switch back to `lmsysorg/sglang`) |
| `image.tag` | `v0.5.12-xeon-fix11-debug` | Pinned to the validated build |
| `image.pullPolicy` | `IfNotPresent` | Set to `Never` if the image is only in local containerd |
| `modelSource` | `Qwen/Qwen3-8B` | HuggingFace repo to load |
| `modelName` | `qwen3-8b` | Served name (also used in route URI) |
| `server.dtype` | `bfloat16` | Compute dtype |
| `server.extraArgs` | `[]` | Extra CLI flags to `sglang serve` |
| `server.maxTotalTokens` | `32768` | Caps KV-cache memory (sglang reads host RAM, not cgroup limits) |
| `extraEnv` | `[MXFP4_NIBBLE_ORDER=low_first]` | Env vars; the default is required for correct MXFP4 weight decode |
| `oidc.enabled` | `true` | Enable APISIX `openid-connect` plugin |
| `apisixRoute.enabled` | `true` | Create `ApisixRoute` for the service |
| `ingress.enabled` | `true` | Create `Ingress` for the service |
| `huggingface.token` | `""` | Required for gated models (e.g. `meta-llama/*`) |

The complete configuration surface is documented inline in `values.yaml`.

### Debug Env Vars (off by default, baked into the image)

| Variable | Effect |
|----------|--------|
| `ALLOW_FP32_MXFP4=1` | Lets you pass `--dtype float32` with MXFP4 models |
| `MXFP4_OUT_DTYPE=float32\|float16\|bfloat16` | Dequant output dtype |
| `FP32_PROMOTE_MOE=1` | Compute per-expert MoE forward in fp32 |
| `--kv-cache-dtype float32` | Allowed by our patched allowlist (allocates fp32 KV) |

These were used during a precision investigation A/B; see commit history
on `cld2labs/sglang-gpt-oss` for context.

## 🩹 What's Patched

The image-build directory contains a series of small Python patches
applied to sglang's installed source at image build time:

| # | Patch | Purpose |
|---|-------|---------|
| 1 | (Dockerfile step 1) | Rebuild `sgl-kernel` with `-mavx512bf16 -mamx-bf16` so bf16 matmuls emit `vdpbf16ps` instead of crashing with "scalar path not implemented" |
| 2 | `enable-mxfp4-cpu.py` | Register `mxfp4` quantization for CPU (upstream gates it behind `is_cuda() or is_hip()`) |
| 2b | `enable-gpt-oss-cpu.py` | Add `torch_native`/`intel_amx` to GptOss's CPU attention-backend allowlist |
| 3 | `enable-gpt-oss-cpu-loaders.py` | Guard `.cuda()` calls in gpt-oss weight loaders for CPU-only torch |
| 4 | `enable-gpt-oss-cpu-moe.py` | Add a CPU branch to `Mxfp4MoEMethod` that dequants MXFP4 → bf16 at load time |
| 5 | `enable-cpu-sinks-attention.py` | Add sinks-attention support to `torch_native_backend` |
| 6/7 | `enable-gpt-oss-cpu-dequant-v2.py` | Self-contained MXFP4 dequant with explicit nibble-order control |
| 8 | `enable-gpt-oss-cpu-moe-v2.py` | Route the MoE forward through `moe_forward_native` so gpt-oss's swiglu+α+clamp+biases is computed correctly |
| 9–11 | `enable-*-debug.py` | Precision debug knobs (off by default; see the env-var table above) |

Patch 1 is a **genuine upstream regression** that affects every Xeon
sglang user, not just gpt-oss — the published image's sgl-kernel `.so`
contains zero AVX-512-BF16 instructions, so any bf16 forward pass
crashes with `tinygemm_kernel_nn: scalar path not implemented!`.

## ⚠️ Known Limitations

- **Long-form drift after ~150 tokens.** With the current pure-Python
  CPU MoE path, output past ~150 tokens collapses into broken tokens,
  emoji, and special-token leaks. Phase 2 ran a full precision A/B
  (`FP32_PROMOTE_MOE`, fp32 KV cache, `--enable-fp32-lm-head`) and
  conclusively ruled out precision as the cause. Surviving hypotheses:
  sliding-window-attention bookkeeping in our patched `torch_native_backend`,
  or Harmony channel-switch tokenization interacting with the sinks wrapper.
- **Throughput.** The chart routes through `moe_forward_native` for
  correctness, not speed; expect ~4 tok/s. The faster `fused_experts_cpu`
  kernel does plain `silu(gate)*up` and cannot be used directly for
  gpt-oss.
- **No tensor parallelism.** Chart currently runs `--tp-size=1`. Setting
  `--tp-size=2` to split across NUMA nodes should give multi-x speedup
  but the patch stack has not been validated under TP.

## 🔧 Troubleshooting

### View Logs

```bash
kubectl logs -l app=sglang -f
kubectl describe pod -l app=sglang
```

### Common Issues

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `Unknown quantization method: mxfp4` | Pod is using the upstream image | Confirm `image.repository=enterprise-inference/sglang` and `image.tag=v0.5.12-xeon-fix11-debug` |
| Pod OOMKilled at startup | sglang reads host RAM, not cgroup limits | Lower `server.maxTotalTokens` or raise `resources.limits.memory` |
| `tinygemm_kernel_nn: scalar path not implemented!` | Wrong (upstream) sgl-kernel `.so` is loaded | Rebuild with `image-build/build-and-import.sh` |
| Random-vocab gibberish in `content` | Wrong MXFP4 nibble order | Verify `MXFP4_NIBBLE_ORDER=low_first` is in pod env |
| `content: null` in response | gpt-oss spent all `max_tokens` reasoning | Raise `max_tokens` to ≥ 150 |
| 504 from nginx/APISIX | Default 60s proxy timeout vs ~4 tok/s CPU inference | Bump `nginx.ingress.kubernetes.io/proxy-read-timeout` and `ApisixRoute.spec.http[].timeout` to 600s |
| 401 from APISIX with a "valid" token | Token issuer claim mismatch | Fetch token via cluster-internal `kubectl run` curl pod (see Inference) |
| Token expires too quickly | Keycloak master realm defaults to 60s | Bump `accessTokenLifespan` via the admin REST API |

### Stop / Restart

```bash
helm uninstall gpt-oss-20b
kubectl delete pvc -l app.kubernetes.io/instance=gpt-oss-20b   # frees the model cache
```

## 📁 Project Structure

```
core/helm-charts/sglang/
├── README.md                     # this file
├── Chart.yaml
├── values.yaml                   # full configuration surface
├── gpt-oss-20b-values.yaml       # canonical override for this model
├── templates/                    # Helm templates (Deployment, Service, PVC, Ingress, ApisixRoute, Secret)
└── image-build/
    ├── Dockerfile                # FROM lmsysorg/sglang:v0.5.12-xeon + 11 patch steps
    ├── build-and-import.sh       # one-shot build + import into k3s containerd
    └── enable-*.py               # patch scripts applied at image build time
```

## 📚 References

- [SGLang documentation](https://docs.sglang.io)
- [SGLang CPU server guide](https://docs.sglang.io/docs/hardware-platforms/cpu_server)
- [OpenAI gpt-oss model card](https://huggingface.co/openai/gpt-oss-20b)

---

## 📎 Appendix: From-Scratch Bootstrap

Use this only if you're standing up a fresh single-node box without OPEA's
Ansible-driven cluster setup. On a stock OPEA cluster, k3s, nginx-ingress,
APISIX, and Keycloak are already in place and you can skip directly to
🚀 **Deploy**.

### A.1 k3s + Helm

```bash
sudo bash scripts/bootstrap-k3s.sh
export KUBECONFIG=$HOME/.kube/config
kubectl get nodes -o wide
helm version --short
```

The script installs k3s (`--disable traefik`), symlinks `kubectl`, copies
kubeconfig to `~/.kube/config`, and installs Helm 3.

### A.2 nginx-ingress

```bash
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm install ingress-nginx ingress-nginx/ingress-nginx \
  -n ingress-nginx --create-namespace \
  --set controller.service.type=NodePort \
  --set controller.service.nodePorts.http=30080 \
  --set controller.service.nodePorts.https=30443 \
  --set controller.admissionWebhooks.enabled=false \
  --set controller.ingressClassResource.default=true

kubectl wait --for=condition=ready pod -n ingress-nginx \
  -l app.kubernetes.io/component=controller --timeout=120s
```

### A.3 Keycloak (dev mode)

```bash
kubectl apply -f - <<'EOF'
apiVersion: apps/v1
kind: Deployment
metadata: { name: keycloak, namespace: default }
spec:
  replicas: 1
  selector: { matchLabels: { app: keycloak } }
  template:
    metadata: { labels: { app: keycloak } }
    spec:
      containers:
      - name: keycloak
        image: quay.io/keycloak/keycloak:26.0
        args: ["start-dev"]
        env:
        - { name: KEYCLOAK_ADMIN,          value: admin }
        - { name: KEYCLOAK_ADMIN_PASSWORD, value: admin }
        - { name: KC_HTTP_RELATIVE_PATH,   value: "/" }
        - { name: KC_PROXY,                value: edge }
        ports: [{ containerPort: 8080, name: http }]
---
apiVersion: v1
kind: Service
metadata: { name: keycloak, namespace: default }
spec:
  selector: { app: keycloak }
  ports: [{ port: 80, targetPort: 8080 }]
EOF
kubectl wait --for=condition=ready pod -l app=keycloak --timeout=300s
```

Create the OIDC client (`my-client-id` with the secret the chart expects):

```bash
ADMIN=$(kubectl run kc-admin --rm -i --restart=Never --quiet \
  --image=curlimages/curl:8.10.1 -- \
  sh -c 'curl -sS -X POST http://keycloak.default.svc.cluster.local/realms/master/protocol/openid-connect/token \
    -d "client_id=admin-cli" -d "username=admin" -d "password=admin" -d "grant_type=password"' \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['access_token'])")

kubectl run kc-create --rm -i --restart=Never --quiet \
  --image=curlimages/curl:8.10.1 -- \
  sh -c "curl -sS -X POST -H 'Authorization: Bearer $ADMIN' \
    -H 'Content-Type: application/json' \
    http://keycloak.default.svc.cluster.local/admin/realms/master/clients \
    -d '{\"clientId\":\"my-client-id\",\"secret\":\"tf29wNR5fZ7edbNmnLSWDEvL7Simx4CR\",\"serviceAccountsEnabled\":true,\"publicClient\":false,\"directAccessGrantsEnabled\":true}'"
```

### A.4 APISIX

```bash
helm repo add apisix https://charts.apiseven.com
helm install auth-apisix apisix/apisix \
  -n auth-apisix --create-namespace \
  --set service.type=NodePort \
  --set ingress-controller.enabled=true \
  --set ingress-controller.config.apisix.serviceNamespace=auth-apisix

kubectl wait --for=condition=ready pod -n auth-apisix --all --timeout=300s
```

APISIX v2 ingress controller also requires a `GatewayProxy` CRD and an
updated `IngressClass parameters` link before it will accept routes;
see the in-cluster `kubectl describe apisixroute` output for guidance
if the controller returns "Route Not Found" for an otherwise valid
ApisixRoute.

### A.5 TLS Cert for `api.example.com`

```bash
openssl req -x509 -newkey rsa:2048 -nodes -days 365 \
  -keyout /tmp/tls.key -out /tmp/tls.crt \
  -subj "/CN=api.example.com" \
  -addext "subjectAltName=DNS:api.example.com"

kubectl create secret tls api-example-com-tls \
  --cert=/tmp/tls.crt --key=/tmp/tls.key -n default
```

Now proceed to 🛠️ **Build the Image** and 🚀 **Deploy** above.
