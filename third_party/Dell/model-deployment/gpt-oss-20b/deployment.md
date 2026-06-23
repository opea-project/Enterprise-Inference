## Step 1: Prerequisites to Deploy gpt-oss-20b Model on Xeon with Keycloak

Ensure the Enterprise Inference stack with Keycloak is already deployed
before proceeding. If you're standing the cluster up from scratch
yourself, the appendix in `core/helm-charts/sglang/README.md` walks the
full bootstrap.

Edit `core/scripts/generate-token.sh` and set your values before
sourcing it:

| Variable                  | Description                                                              |
| ------------------------- | ------------------------------------------------------------------------ |
| `BASE_URL`                | Hostname of your cluster (e.g. `api.example.com`), without `https://`   |
| `KEYCLOAK_ADMIN_USERNAME` | Keycloak admin username                                                  |
| `KEYCLOAK_PASSWORD`       | Keycloak admin password                                                  |
| `KEYCLOAK_CLIENT_ID`      | Keycloak client ID configured during EI deployment                       |

Then run:

```bash
export HUGGING_FACE_HUB_TOKEN="your_token_here"

cd ~/Enterprise-Inference
source core/scripts/generate-token.sh
```

This exports: `BASE_URL`, `KEYCLOAK_CLIENT_ID`, `KEYCLOAK_CLIENT_SECRET`,
and `TOKEN`. Verify with:

```bash
echo "BASE_URL=$BASE_URL"
echo "TOKEN length=${#TOKEN}  (expect 1000+; empty means the script failed silently)"
```

> Empty `TOKEN` means the script could not reach
> `https://${BASE_URL}/realms/master/...` or `https://${BASE_URL}/token`.
> The EI deployment provisions both as ingress routes to Keycloak — if
> they're missing, the cluster bootstrap is incomplete; see Appendix
> A.7 of the chart README.

## Step 2: Build the Patched SGLang Image

gpt-oss-20b ships natively in MXFP4 quantization, and the upstream
`lmsysorg/sglang:v0.5.12-xeon` image cannot serve it on CPU (MXFP4 is
GPU-gated, sinks attention is unsupported on the CPU backends, and the
published `sgl-kernel` shared library is missing the AVX-512-BF16
compile flags needed for any bf16 matmul).

The SGLang chart ships a one-shot build script that produces a patched
image and loads it directly into the local containerd image store. No
external registry is required.

```bash
sudo bash core/helm-charts/sglang/image-build/build-and-import.sh
```

First run takes ~5-10 minutes. The script auto-detects the runtime —
`nerdctl` on a kubeadm/containerd cluster (what `inference-stack-deploy.sh`
produces) or `k3s ctr` on a k3s cluster. Verify with whichever matches
your cluster:

```bash
# kubeadm / containerd
sudo nerdctl --namespace k8s.io images | grep enterprise-inference/sglang

# k3s
sudo k3s ctr images ls | grep enterprise-inference/sglang
```

Either should report `enterprise-inference/sglang:v0.5.12-xeon-fix11-debug`.

For a detailed breakdown of what each patch does, see
`core/helm-charts/sglang/README.md` (section: What's Patched).

## Step 3: Deploy gpt-oss-20b

```bash
helm install sglang-gpt-oss-20b ./core/helm-charts/sglang \
  --set modelSource="openai/gpt-oss-20b" \
  --set modelName="gpt-oss-20b" \
  --set huggingface.token="$HUGGING_FACE_HUB_TOKEN" \
  --set ingress.enabled=true \
  --set ingress.secretName="${BASE_URL}" \
  --set ingress.host="${BASE_URL}" \
  --set oidc.clientId="$KEYCLOAK_CLIENT_ID" \
  --set oidc.clientSecret="$KEYCLOAK_CLIENT_SECRET" \
  --set apisixRoute.enabled=true \
  --set 'server.extraArgs={--attention-backend,torch_native,--reasoning-parser,gpt-oss,--tool-call-parser,gpt-oss}'
```

The chart's `values.yaml` already targets the patched image, sets bf16,
sizes resources for a Xeon node, and enables the
`MXFP4_NIBBLE_ORDER=low_first` env var required for correct MXFP4
weight decode. The `--set` above adds the gpt-oss-specific runtime
flags (Harmony reasoning/tool-call parsers, CPU attention backend) and
the per-cluster ingress/OIDC overrides.

## Step 4: Verify the Deployment

```bash
kubectl get pods
kubectl get apisixroutes
```

Expected output (the sglang pod is what matters here; your existing
Keycloak / APISIX / ingress pods will appear in the listing too, with
names that depend on how those components were deployed in your
cluster):

```
NAME                                          READY   STATUS    RESTARTS
sglang-gpt-oss-20b-<hash>-<hash>              1/1     Running   0
...                                           1/1     Running   0   # keycloak, apisix, ingress-nginx, etc.
```

> Note: First pod start takes ~4-5 minutes (downloading ~12 GB of
> weights from Hugging Face, then dequantizing MXFP4 → bf16 in memory).
> Subsequent restarts are fast because the cache PVC persists the
> weights.

```
NAME                                       HOSTS
sglang-gpt-oss-20b-apisixroute             api.example.com
```

## Step 5: Test the Deployed Model

```bash
curl -k https://${BASE_URL}/gpt-oss-20b-sglang/v1/chat/completions \
  -X POST \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "model": "gpt-oss-20b",
    "messages": [{"role": "user", "content": "In one sentence, what is deep learning?"}],
    "max_tokens": 150,
    "temperature": 0.3
  }'
```

> The exact `${BASE_URL}` value depends on how the cluster was
> bootstrapped — it's what `core/scripts/generate-token.sh` exports
> after sourcing. Self-bootstrapped clusters following the chart
> README's appendix will have `${BASE_URL}=api.example.com:30443`.

If successful, the model returns a chat-completion response with the
answer in `choices[0].message.content` and the model's internal
reasoning in `choices[0].message.reasoning_content`.

> If the request times out with a 504, CPU inference at ~4 tokens/s can exceed the default 60 s upstream timeout for longer responses. See [Gateway Timeout (504)](../sglang-troubleshooting.md#1-gateway-timeout-504-on-inference-requests) in the troubleshooting guide to bump both the nginx and APISIX timeouts.

### A Note on `max_tokens`

gpt-oss uses the Harmony chat format: every response starts in an
internal "analysis" channel and only switches to the user-visible
"final" channel when reasoning is complete. With small budgets the
model spends them all reasoning and the `content` field comes back null:

| `max_tokens` | What you'll see                                    |
| ------------ | -------------------------------------------------- |
| ≤ 100        | `content: null`, reasoning truncated               |
| 150          | One short sentence — good for quick verification   |
| 300          | Paragraph with light formatting                    |
| > 400        | Hits documented long-form drift (see troubleshooting) |

## To Undeploy the Model

```bash
helm uninstall sglang-gpt-oss-20b
kubectl delete pvc -l app.kubernetes.io/instance=sglang-gpt-oss-20b   # frees the cached weights
```

## Parameters

| Parameter | Description |
| --------- | ----------- |
| `--set modelSource="openai/gpt-oss-20b"` | HuggingFace repo to load (passed to `sglang serve --model-path`). |
| `--set modelName="gpt-oss-20b"` | Served name, also used in the ApisixRoute URI prefix `/gpt-oss-20b-sglang/*`. |
| `--set huggingface.token="..."` | HF token for gated models. `openai/gpt-oss-20b` is public, so leave empty. |
| `--set ingress.enabled=true` | Creates a Kubernetes Ingress that terminates TLS at nginx. |
| `--set ingress.host="${BASE_URL}"` | Hostname the ingress matches (same value used in the TLS secret name). |
| `--set ingress.secretName="${BASE_URL}"` | TLS Secret used at the ingress layer — its name equals the hostname by chart convention. |
| `--set oidc.clientId="..."` | Keycloak OIDC client ID; APISIX validates tokens against this client. |
| `--set oidc.clientSecret="..."` | Keycloak OIDC client secret. |
| `--set apisixRoute.enabled=true` | Creates the APISIX route with `openid-connect` plugin for bearer validation. |
| `--set 'server.extraArgs={...}'` | gpt-oss-specific runtime flags: `torch_native` CPU attention backend, Harmony `--reasoning-parser` and `--tool-call-parser`. |
