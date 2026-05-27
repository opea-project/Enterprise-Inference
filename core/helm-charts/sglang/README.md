# SGLang Helm Chart — Intel Xeon CPU

## Overview

Deploys [SGLang](https://github.com/sgl-project/sglang) on a Kubernetes
cluster as a model-agnostic inference server on Intel Xeon CPU nodes,
including the OPEA-standard nginx-ingress → APISIX → Keycloak (OIDC)
auth chain.

The chart has **no built-in default model** — `modelSource` and
`modelName` must be supplied at install time, either via `--set` or a
values file. Model-specific recipes (helm command, values overrides,
model card) live under `third_party/Dell/model-deployment/<model-name>/`.
Notable example: **gpt-oss-20b**, which required a patched SGLang image
to work on CPU (see [Noteworthy: gpt-oss-20b](#noteworthy-gpt-oss-20b)
below).

The chart targets a **patched** SGLang image (`enterprise-inference/sglang:v0.5.12-xeon-fix11-debug`).
The most important patch (fix1) rebuilds `sgl-kernel` with the correct
AVX-512-BF16 / AMX-BF16 compile flags — the upstream
`lmsysorg/sglang:v0.5.12-xeon` ships the shared library without them, so
every bf16 forward pass crashes with `tinygemm_kernel_nn: scalar path
not implemented!` regardless of model. The remaining patches are
gpt-oss-specific and are runtime no-ops for other models. The image is
built once via a self-contained Dockerfile and imported directly into
k3s containerd — no registry required.

## Features

- **Model-agnostic SGLang on Xeon CPU** — any HF model SGLang supports loads through the same chart
- **Patched image** that unblocks bf16 inference on Xeon (every model benefits) and adds MXFP4 + sinks-attention support for gpt-oss
- **OPEA-standard auth chain**: TLS at nginx, OIDC bearer validation at APISIX, token issuance by Keycloak
- **No external registry**: image builds locally and imports into k3s containerd
- **OpenAI-compatible API**: `/v1/chat/completions`, `/v1/models`, `/v1/completions`
- **Chart-only delivery**: same standalone pattern as `core/helm-charts/ovms`, not yet wired into the Ansible playbooks

## Prerequisites

- **Operating System**: Ubuntu 22.04+
- **Hardware**: Intel Xeon with AVX-512-BF16 / AMX-BF16 (Sapphire Rapids, Emerald Rapids, Granite Rapids)
- **Memory**: ≥ 64 GiB RAM for mid-size models (gpt-oss-20b uses ~25 GiB dequantized + KV cache)
- **Disk**: ≥ 100 GiB free on the root partition
- **Kubernetes**: 1.24+ (k3s is fine; this chart was validated on single-node k3s)
- **Helm**: 3+
- **NodePorts free on the host**: 30080, 30443 (nginx), 32080 (APISIX)
- **HuggingFace token** for gated models (e.g. `meta-llama/*`); not required for open models like `openai/gpt-oss-20b` or `Qwen/Qwen3-8B`
- **Sudo access** for the one-shot image build

> **Note:** On a stock OPEA cluster, k3s, nginx-ingress, APISIX, and Keycloak
> are already in place via the project's Ansible playbooks — skip straight to
> **Build the Image**. The "From-Scratch Bootstrap" appendix at the bottom is only
> for people standing up a fresh single-node box from zero.

## Build the Image

```bash
git clone https://github.com/cld2labs/Enterprise-Inference.git
cd Enterprise-Inference
git checkout cld2labs/sglang-gpt-oss

sudo bash core/helm-charts/sglang/image-build/build-and-import.sh
```

First run takes ~5–10 minutes (installs docker.io if missing, compiles
27 C++ files in `sgl-kernel` with the right BF16 flags, runs 11 Python
patch scripts against SGLang's in-image source, and imports the result
into k3s containerd).

Verify:

```bash
sudo k3s ctr images ls | grep enterprise-inference/sglang
# docker.io/enterprise-inference/sglang:v0.5.12-xeon-fix11-debug
```

## Deploy a Model

`modelSource` and `modelName` are required at install time. The chart
template fails fast if either is empty.

### Generic install

```bash
helm install <release-name> ./core/helm-charts/sglang \
  --set modelSource="<huggingface/org/model>" \
  --set modelName="<release-friendly-name>" \
  --set huggingface.token="$HF_TOKEN"   # only if the model is gated
```

### Model-specific recipes

Models that need additional configuration ship with their own values file
and deployment guide:

| Model | Deployment guide |
| ----- | ---------------- |
| `openai/gpt-oss-20b` | `third_party/Dell/model-deployment/gpt-oss-20b/deployment.md` |

The deployment guide carries the full `helm install` command line for
that model — all model-specific flags (parsers, attention backend,
extraArgs) come through as `--set` overrides. The chart's own
`values.yaml` stays model-agnostic.

Wait for the pod (first start downloads the weights — duration depends
on model size and network):

```bash
kubectl wait --for=condition=ready pod -l app=sglang --timeout=600s
kubectl logs -l app=sglang --tail=5
# expect: INFO: Uvicorn running on http://0.0.0.0:30000
```

## Inference

### Smoke test (no auth, via port-forward)

```bash
kubectl port-forward svc/<release-name>-sglang 30000:30000 &
sleep 2

curl -sS http://localhost:30000/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "<modelName>",
    "messages": [{"role":"user","content":"In one sentence, what is deep learning?"}],
    "max_tokens": 150,
    "temperature": 0.3
  }' | python3 -m json.tool
```

### Auth-routed call (nginx → APISIX → Keycloak → sglang)

Fetch a token from inside the cluster (so the `iss` claim matches what
APISIX validates against), then call through the ingress:

```bash
TOKEN=$(kubectl run keycloak-tok --rm -i --restart=Never --quiet \
  --image=curlimages/curl:8.10.1 -- \
  sh -c 'curl -sS -X POST http://keycloak.default.svc.cluster.local/realms/master/protocol/openid-connect/token \
    -d "client_id=my-client-id" \
    -d "client_secret=<your-client-secret>" \
    -d "grant_type=client_credentials"' \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['access_token'])")

curl -sSk https://localhost:30443/<modelName>-sglang/v1/chat/completions \
  -H "Host: api.example.com" \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "<modelName>",
    "messages": [{"role":"user","content":"In one sentence, what is deep learning?"}],
    "max_tokens": 150,
    "temperature": 0.3
  }' | python3 -m json.tool
```

### API endpoints

| Endpoint | Description |
|----------|-------------|
| `/v1/models` | List loaded models |
| `/v1/chat/completions` | OpenAI-compatible chat completions |
| `/v1/completions` | OpenAI-compatible text completions |
| `/health` | Liveness probe |

## Configuration

### Key values

| Key | Default | Description |
|-----|---------|-------------|
| `image.repository` | `enterprise-inference/sglang` | Patched image (set to `lmsysorg/sglang` to use upstream, but bf16 inference will crash) |
| `image.tag` | `v0.5.12-xeon-fix11-debug` | Pinned to the validated build |
| `image.pullPolicy` | `IfNotPresent` | Set to `Never` if the image is only in local containerd |
| `modelSource` | _(required)_ | HuggingFace repo to load (chart fails to render if empty) |
| `modelName` | _(required)_ | Served name (also used in route URI; chart fails if empty) |
| `server.dtype` | `bfloat16` | Compute dtype |
| `server.extraArgs` | `[]` | Extra CLI flags to `sglang serve` |
| `server.maxTotalTokens` | `32768` | Caps KV-cache memory (SGLang reads host RAM, not cgroup limits) |
| `extraEnv` | `[MXFP4_NIBBLE_ORDER=low_first]` | Env vars; the default is required for MXFP4 models and a runtime no-op for others |
| `oidc.enabled` | `true` | Enable APISIX `openid-connect` plugin |
| `apisixRoute.enabled` | `true` | Create `ApisixRoute` for the service |
| `ingress.enabled` | `true` | Create `Ingress` for the service |
| `huggingface.token` | `""` | Required for gated models (e.g. `meta-llama/*`) |

The complete configuration surface is documented inline in `values.yaml`.

### Debug env vars (off by default, baked into the image)

| Variable | Effect | Applies to |
| -------- | ------ | ---------- |
| `ALLOW_FP32_MXFP4=1` | Lets you pass `--dtype float32` with MXFP4 models | MXFP4 models only |
| `MXFP4_OUT_DTYPE=float32\|float16\|bfloat16` | Dequant output dtype | MXFP4 models only |
| `FP32_PROMOTE_MOE=1` | Compute per-expert MoE forward in fp32 | MoE models only |
| `--kv-cache-dtype float32` | Allowed by our patched allowlist (allocates fp32 KV) | All models |

These were used during a precision investigation A/B; see commit history
on `cld2labs/sglang-gpt-oss` for context.

## What's Patched

The image-build directory contains a series of small Python patches
applied to SGLang's installed source at image build time:

| # | Patch | Scope | Purpose |
|---|-------|-------|---------|
| 1 | (Dockerfile step 1) | **All bf16 models** | Rebuild `sgl-kernel` with `-mavx512bf16 -mamx-bf16` so bf16 matmuls emit `vdpbf16ps` instead of crashing with "scalar path not implemented" |
| 2 | `enable-mxfp4-cpu.py` | MXFP4 models | Register `mxfp4` quantization for CPU (upstream gates it behind `is_cuda() or is_hip()`) |
| 2b | `enable-gpt-oss-cpu.py` | gpt-oss | Add `torch_native`/`intel_amx` to GptOss's CPU attention-backend allowlist |
| 3 | `enable-gpt-oss-cpu-loaders.py` | gpt-oss | Guard `.cuda()` calls in gpt-oss weight loaders for CPU-only torch |
| 4 | `enable-gpt-oss-cpu-moe.py` | MXFP4 MoE | Add a CPU branch to `Mxfp4MoEMethod` that dequants MXFP4 → bf16 at load time |
| 5 | `enable-cpu-sinks-attention.py` | sinks-attention models (gpt-oss) | Add sinks-attention support to `torch_native_backend` |
| 6/7 | `enable-gpt-oss-cpu-dequant-v2.py` | MXFP4 models | Self-contained MXFP4 dequant with explicit nibble-order control via `MXFP4_NIBBLE_ORDER` |
| 8 | `enable-gpt-oss-cpu-moe-v2.py` | gpt-oss | Route the MoE forward through `moe_forward_native` so gpt-oss's swiglu+α+clamp+biases is computed correctly |
| 9–11 | `enable-*-debug.py` | Debug knobs | Precision A/B knobs (off by default; see env-var table above) |

Patch 1 is a **genuine upstream regression** that affects every Xeon
SGLang user, not just gpt-oss — the published image's `sgl-kernel` `.so`
contains zero AVX-512-BF16 instructions, so any bf16 forward pass
crashes with `tinygemm_kernel_nn: scalar path not implemented!`.

Patches 2–8 are **gpt-oss-specific** in scope. They are runtime no-ops
for models that don't trigger them (e.g. a Qwen3 deployment never enters
the MXFP4 dequant path or the sinks-attention wrapper), so leaving them
baked into the image carries no cost for other models.

## Noteworthy: gpt-oss-20b

`openai/gpt-oss-20b` is the most complex model this chart serves and the
driver for most of the patch stack above. Specifically:

- **MXFP4 quantization is GPU-gated upstream.** Patches 2, 4, 6/7 enable
  it on CPU by registering the quantization method and adding a CPU
  weight-load dequant path (MXFP4 → bf16 at startup).
- **gpt-oss uses sinks attention** (a learnable per-head scalar added to
  the softmax denominator). No upstream CPU attention backend supports
  it; patch 5 adds it to `torch_native_backend`.
- **MoE forward needs gpt-oss-specific math** (swiglu + α + clamp +
  biases). Patch 8 routes through `moe_forward_native`, which handles
  this correctly at the cost of throughput vs the AMX kernel.

The full deployment recipe — model card, helm command, verification,
parameter reference — is in
[`third_party/Dell/model-deployment/gpt-oss-20b/`](../../third_party/Dell/model-deployment/gpt-oss-20b/).

**Known limitations specific to gpt-oss-20b:**

- **Long-form drift after ~150 tokens.** Output past ~150 tokens
  collapses into broken tokens, emoji, and special-token leaks. A
  precision A/B (fp32 per-expert MoE, fp32 KV cache,
  `--enable-fp32-lm-head`) conclusively ruled out precision as the
  cause. Surviving hypotheses: sliding-window-attention bookkeeping in
  our patched `torch_native_backend`, or Harmony channel-switch
  tokenization interacting with the sinks wrapper.
- **Throughput.** The chart routes through `moe_forward_native` for
  correctness, not speed; expect ~4 tok/s.
- **No tensor parallelism.** Chart currently runs `--tp-size=1`. Setting
  `--tp-size=2` to split across NUMA nodes should give multi-x speedup
  but the patch stack has not been validated under TP.

## Troubleshooting

See [`third_party/Dell/model-deployment/sglang-troubleshooting.md`](../../third_party/Dell/model-deployment/sglang-troubleshooting.md)
for a symptom-indexed guide covering:

- Gateway Timeout (504) on inference requests
- Response `content` field is null (gpt-oss Harmony format)
- "Unknown quantization method: mxfp4" at startup
- "scalar path not implemented!" on the first forward pass
- Random-vocab gibberish in `content` (nibble order)
- Long-form drift past ~150 tokens (gpt-oss)
- 401 Unauthorized from APISIX with a valid-looking token (issuer mismatch)

Quick log + describe:

```bash
kubectl logs -l app=sglang -f
kubectl describe pod -l app=sglang
```

### Stop / restart

```bash
helm uninstall <release-name>
kubectl delete pvc -l app.kubernetes.io/instance=<release-name>   # frees the model cache
```

## Project Structure

```
core/helm-charts/sglang/
├── README.md                     # this file
├── Chart.yaml
├── values.yaml                   # full configuration surface
├── templates/                    # Helm templates (Deployment, Service, PVC, Ingress, ApisixRoute, Secret)
└── image-build/
    ├── Dockerfile                # FROM lmsysorg/sglang:v0.5.12-xeon + 11 patch steps
    ├── build-and-import.sh       # one-shot build + import into k3s containerd
    └── enable-*.py               # patch scripts applied at image build time

third_party/Dell/model-deployment/
├── sglang-troubleshooting.md     # symptom-indexed troubleshooting for the SGLang chart
└── gpt-oss-20b/
    ├── model-card.md             # gpt-oss-20b model card
    └── deployment.md             # gpt-oss-20b deployment guide (carries the full helm command)
```

## References

- [SGLang documentation](https://docs.sglang.io)
- [SGLang CPU server guide](https://docs.sglang.io/docs/hardware-platforms/cpu_server)
- [OpenAI gpt-oss model card](https://huggingface.co/openai/gpt-oss-20b)

---

## Appendix: From-Scratch Bootstrap

Use this only if you're standing up a fresh single-node box without OPEA's
Ansible-driven cluster setup. On a stock OPEA cluster, k3s, nginx-ingress,
APISIX, and Keycloak are already in place and you can skip directly to
**Build the Image**.

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
        - { name: KC_PROXY_HEADERS,        value: xforwarded }
        # Pin the issuer hostname so tokens are always stamped with the
        # cluster-internal name, no matter which edge hostname the
        # request came in on. APISIX validates the `iss` claim against
        # this hostname (chart's oidc.discovery default).
        - { name: KC_HOSTNAME,             value: "http://keycloak.default.svc.cluster.local" }
        - { name: KC_HOSTNAME_STRICT,      value: "false" }
        - { name: KC_HOSTNAME_BACKCHANNEL_DYNAMIC, value: "false" }
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

Create the OIDC client. The `clientId` and `secret` here must exactly
match what you'll later pass to the chart via `--set oidc.clientId=...`
and `--set oidc.clientSecret=...`. The values below are the appendix
defaults used by the gpt-oss-20b deployment guide — substitute your
own for any non-test deployment.

```bash
ADMIN=$(kubectl run kc-admin --rm -i --restart=Never --quiet \
  --image=curlimages/curl:8.10.1 -- \
  sh -c 'curl -sS -X POST http://keycloak.default.svc.cluster.local/realms/master/protocol/openid-connect/token \
    -d "client_id=admin-cli" -d "username=admin" -d "password=admin" -d "grant_type=password"' \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['access_token'])")

CLIENT_ID=my-client-id
CLIENT_SECRET=tf29wNR5fZ7edbNmnLSWDEvL7Simx4CR

kubectl run kc-create --rm -i --restart=Never --quiet \
  --image=curlimages/curl:8.10.1 -- \
  sh -c "curl -sS -X POST -H 'Authorization: Bearer $ADMIN' \
    -H 'Content-Type: application/json' \
    http://keycloak.default.svc.cluster.local/admin/realms/master/clients \
    -d '{\"clientId\":\"${CLIENT_ID}\",\"secret\":\"${CLIENT_SECRET}\",\"serviceAccountsEnabled\":true,\"publicClient\":false,\"directAccessGrantsEnabled\":true}'"
```

Verify the client was created:

```bash
kubectl run kc-check --rm -i --restart=Never --quiet \
  --image=curlimages/curl:8.10.1 -- \
  sh -c "curl -sS -X POST http://keycloak.default.svc.cluster.local/realms/master/protocol/openid-connect/token \
    -d 'client_id=${CLIENT_ID}' -d 'client_secret=${CLIENT_SECRET}' -d 'grant_type=client_credentials'" \
  | head -c 80
# expect: JSON with "access_token":"..."
```

### A.4 APISIX

The Apache APISIX chart installs the dataplane + etcd + ingress
controller. On v2 of the ingress controller (current as of this writing)
you additionally need a `GatewayProxy` CR and an `IngressClass` whose
`parameters` reference it — without those, the controller silently drops
every `ApisixRoute` and the chart's route ends up unreachable.

```bash
helm repo add apisix https://charts.apiseven.com
helm install auth-apisix apisix/apisix \
  -n auth-apisix --create-namespace \
  --set service.type=NodePort \
  --set ingress-controller.enabled=true \
  --set ingress-controller.config.apisix.serviceNamespace=auth-apisix

kubectl wait --for=condition=ready pod -n auth-apisix --all --timeout=300s

# Grab the admin key the chart generated for the dataplane
ADMIN_KEY=$(helm get values auth-apisix -n auth-apisix --all \
  | python3 -c "import sys,yaml; print(yaml.safe_load(sys.stdin)['apisix']['admin']['credentials']['admin'])")
echo "APISIX admin key: $ADMIN_KEY"

# Create the GatewayProxy that the ingress controller will use as its
# dataplane handle.
kubectl apply -f - <<EOF
apiVersion: apisix.apache.org/v1alpha1
kind: GatewayProxy
metadata:
  name: apisix-proxy
  namespace: auth-apisix
spec:
  provider:
    type: ControlPlane
    controlPlane:
      endpoints:
        - http://auth-apisix-admin.auth-apisix.svc.cluster.local:9180
      auth:
        type: AdminKey
        adminKey:
          value: "${ADMIN_KEY}"
EOF

# Patch the IngressClass `apisix` (which the chart created) to point at
# the GatewayProxy we just made.
kubectl patch ingressclass apisix --type='merge' -p '{
  "spec": {
    "parameters": {
      "apiGroup": "apisix.apache.org",
      "kind": "GatewayProxy",
      "name": "apisix-proxy",
      "namespace": "auth-apisix",
      "scope": "Namespace"
    }
  }
}'

# Verify
kubectl get gatewayproxy -n auth-apisix
kubectl get ingressclass apisix -o jsonpath='{.spec.parameters}{"\n"}'
```

### A.5 TLS cert for `api.example.com`

The chart's `--set ingress.secretName=${BASE_URL}` references a TLS
Secret whose name equals the hostname (so for the appendix default, the
Secret is named `api.example.com`). nginx requires the Secret in the
same namespace as the Ingress that consumes it. We need it in two
places: `auth-apisix` (where the chart-created Ingress for the model
lives) and `default` (where the Keycloak-edge Ingresses in A.7 will
live).

```bash
openssl req -x509 -newkey rsa:2048 -nodes -days 365 \
  -keyout /tmp/tls.key -out /tmp/tls.crt \
  -subj "/CN=api.example.com/O=enterprise-inference-test" \
  -addext "subjectAltName=DNS:api.example.com"

kubectl create secret tls api.example.com \
  --cert=/tmp/tls.crt --key=/tmp/tls.key -n auth-apisix
kubectl create secret tls api.example.com \
  --cert=/tmp/tls.crt --key=/tmp/tls.key -n default
```

### A.6 Hostname resolution for `${BASE_URL}`

`generate-token.sh` and the inference curls in the deployment guide
both hit `https://${BASE_URL}/...` directly, so the host running those
commands must resolve `api.example.com`. In a production EI deployment
this is real DNS pointing at the load balancer; for a self-bootstrapped
cluster, an `/etc/hosts` entry pointing at the node is enough.

```bash
echo "127.0.0.1 api.example.com" | sudo tee -a /etc/hosts
```

nginx in this appendix is on NodePort 30443 (not 443), so set
`BASE_URL` with the port for the EI scripts to find it:

```bash
export BASE_URL=api.example.com:30443
```

### A.7 Keycloak edge routes

`generate-token.sh` issues two HTTP requests against `${BASE_URL}` —
first against `/realms/master/protocol/openid-connect/token` and
`/admin/realms/master/clients/...` (via `keycloak-fetch-client-secret.sh`,
to log in as the admin user and read the OIDC client secret), then
against `/token` (to exchange `client_credentials` for an access token).
On an EI cluster the Ansible playbooks publish all three behind nginx;
when bootstrapping by hand we publish them with two Ingresses below.

```bash
# Pass-through Ingress for /realms/* and /admin/* — these go straight to
# Keycloak's endpoints unmodified.
kubectl apply -f - <<EOF
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: keycloak-edge
  namespace: default
spec:
  ingressClassName: nginx
  tls:
  - hosts: [api.example.com]
    secretName: api.example.com
  rules:
  - host: api.example.com
    http:
      paths:
      - path: /realms
        pathType: Prefix
        backend:
          service: { name: keycloak, port: { number: 80 } }
      - path: /admin
        pathType: Prefix
        backend:
          service: { name: keycloak, port: { number: 80 } }
EOF

# Rewriting Ingress for /token → /realms/master/protocol/openid-connect/token.
# In its own Ingress because the rewrite-target annotation applies to
# every path in the Ingress that holds it.
kubectl apply -f - <<EOF
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: keycloak-token
  namespace: default
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /realms/master/protocol/openid-connect/token
spec:
  ingressClassName: nginx
  tls:
  - hosts: [api.example.com]
    secretName: api.example.com
  rules:
  - host: api.example.com
    http:
      paths:
      - path: /token
        pathType: Exact
        backend:
          service: { name: keycloak, port: { number: 80 } }
EOF
```

Verify the routes work end-to-end (assuming you've done A.6):

```bash
# Should return the realm's public JWKS / configuration
curl -k https://api.example.com:30443/realms/master/.well-known/openid-configuration \
  | python3 -c "import sys,json; c=json.load(sys.stdin); print('issuer:', c['issuer'])"

# Should return an access token for the OIDC client created in A.3
curl -k -s -X POST https://api.example.com:30443/token \
  -d "grant_type=client_credentials" \
  -d "client_id=my-client-id" \
  -d "client_secret=tf29wNR5fZ7edbNmnLSWDEvL7Simx4CR" \
  | python3 -c "import sys,json; t=json.load(sys.stdin); print('token len:', len(t.get('access_token','')))"
```

Now proceed to **Build the Image** and **Deploy a Model** above.
