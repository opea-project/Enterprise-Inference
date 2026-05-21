# SGLang Helm Chart (Xeon CPU build)

Deploys an SGLang inference server using the `lmsysorg/sglang:v0.5.11-xeon` image,
defaulted to serve `openai/gpt-oss-20b` on a single Xeon CPU node.

This chart follows the same standalone pattern as `core/helm-charts/ovms` — it is
not wired into the Ansible playbooks. You deploy it directly with `helm install`.

## Prerequisites

- A Kubernetes cluster with at least one Xeon worker node that has
  - ~80GB free disk (model weights, ~40GB compressed in HF cache)
  - ~96GB RAM available to the pod (bf16 weights + KV + activations)
- `helm` v3+
- (Optional) HuggingFace token if you swap to a gated model. `openai/gpt-oss-20b`
  itself is publicly downloadable.
- (Optional) The auth-apisix + keycloak + nginx-ingress stack from the rest of
  this repo if you want OIDC-protected routing. If you just want to smoke-test
  the model, disable those (see below).

## Quick test (no auth, port-forward)

```bash
helm upgrade --install gpt-oss-20b ./core/helm-charts/sglang \
  --set apisixRoute.enabled=false \
  --set ingress.enabled=false \
  --set oidc.enabled=false

kubectl wait --for=condition=Ready pod \
  -l app.kubernetes.io/instance=gpt-oss-20b --timeout=30m

kubectl port-forward svc/gpt-oss-20b-sglang 30000:30000

# OpenAI-compatible smoke test
curl http://localhost:30000/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "gpt-oss-20b",
    "messages": [{"role": "user", "content": "Say hi in five words."}]
  }'
```

The first start downloads ~40GB of weights into the PVC. Subsequent restarts
reuse the cache.

## Full deploy with auth (matches OVMS pattern)

```bash
helm upgrade --install gpt-oss-20b ./core/helm-charts/sglang \
  --set huggingface.token=$HUGGINGFACE_TOKEN \
  --set ingress.host=api.example.com \
  --set apisixRoute.host=api.example.com
```

The model is then reachable at `https://api.example.com/gpt-oss-20b-sglang/v1/...`.

## Useful overrides

| Flag | Default | Notes |
|---|---|---|
| `modelSource` | `openai/gpt-oss-20b` | Any HF model ID supported by SGLang |
| `modelName` | `gpt-oss-20b` | URL/route path + OpenAI `model` field |
| `server.tpSize` | `1` | Increase for multi-socket parallelism |
| `server.dtype` | `bfloat16` | `bfloat16` recommended on Xeon |
| `server.contextLength` | unset | Override model default context |
| `server.extraArgs` | `[]` | e.g. `'{--mem-fraction-static,0.85}'` |
| `resources.limits.memory` | `96Gi` | Bump up for longer contexts |
| `storage.persistentVolume.size` | `80Gi` | HF cache size on disk |
| `nodeSelector` | `{}` | Pin to a Xeon node label |

## Uninstall

```bash
helm uninstall gpt-oss-20b
```

PVC is deleted by default. Set `--set storage.persistentVolume.deleteOnUninstall=false`
to keep cached weights.
