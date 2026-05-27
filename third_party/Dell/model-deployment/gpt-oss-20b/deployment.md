## Step 1: Obtain a Keycloak Access Token

The deployed model is gated behind APISIX's OIDC validation, so every
inference call must carry a valid bearer token issued by Keycloak. The
mechanics differ depending on whether you're on a production OPEA
cluster or a single-node lab.

### Required exports

The rest of the steps reference these four variables. Pick the path
below that matches your cluster; either path leaves all four exported.

| Variable                | Purpose                                                              |
| ----------------------- | -------------------------------------------------------------------- |
| `BASE_URL`              | Public hostname of the cluster (e.g. `api.example.com`, no `https://`)|
| `KEYCLOAK_CLIENT_ID`    | OIDC client configured in Keycloak                                   |
| `KEYCLOAK_CLIENT_SECRET`| Secret for the OIDC client                                           |
| `TOKEN`                 | Short-lived access token used as `Authorization: Bearer $TOKEN`      |

### Path A — Production OPEA cluster

If your cluster already has the Enterprise Inference stack deployed
(typically via the project's Ansible playbooks), edit
`core/scripts/generate-token.sh` and set the four placeholders to match
your install:

```bash
# core/scripts/generate-token.sh
export BASE_URL=api.example.com           # your cluster's public hostname
export KEYCLOAK_ADMIN_USERNAME=<admin>    # Keycloak admin user
export KEYCLOAK_PASSWORD=<password>       # Keycloak admin password
export KEYCLOAK_CLIENT_ID=my-client-id    # OIDC client created at EI install
```

Then source it (also export `HUGGING_FACE_HUB_TOKEN` if any model in
your deployment requires gated HF access):

```bash
export HUGGING_FACE_HUB_TOKEN="your_token_here"

cd ~/Enterprise-Inference
source core/scripts/generate-token.sh
```

The script logs in to Keycloak as the admin user, fetches the client
secret, and hits `https://${BASE_URL}/token` to exchange it for a
short-lived access token. Verify:

```bash
echo "BASE_URL=$BASE_URL"
echo "TOKEN length=${#TOKEN}  (should be 1000+; empty means the script failed silently)"
```

### Path B — Single-node lab cluster

`generate-token.sh` assumes `https://${BASE_URL}` resolves on port 443
with a real TLS cert. On a single-node lab where `api.example.com` is
only in `/etc/hosts` and nginx is on a NodePort, the script silently
returns an empty `TOKEN`. Use this one-liner instead, which fetches the
token from inside the cluster (so the token's issuer claim matches what
APISIX validates):

```bash
export BASE_URL=api.example.com
export KEYCLOAK_CLIENT_ID=my-client-id
export KEYCLOAK_CLIENT_SECRET=tf29wNR5fZ7edbNmnLSWDEvL7Simx4CR
export HUGGING_FACE_HUB_TOKEN=""          # gpt-oss-20b is public; leave empty

export TOKEN=$(kubectl run keycloak-tok --rm -i --restart=Never --quiet \
  --image=curlimages/curl:8.10.1 -- \
  sh -c "curl -sS -X POST http://keycloak.default.svc.cluster.local/realms/master/protocol/openid-connect/token \
    -d 'client_id=${KEYCLOAK_CLIENT_ID}' \
    -d 'client_secret=${KEYCLOAK_CLIENT_SECRET}' \
    -d 'grant_type=client_credentials'" \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['access_token'])")

echo "TOKEN length=${#TOKEN}"
```

> If `TOKEN length` is `0`, Keycloak rejected the request. The most
> common cause is that the OIDC client doesn't exist in the master
> realm yet — see Appendix A.3 in `core/helm-charts/sglang/README.md`.

## Step 2: Build the Patched SGLang Image

gpt-oss-20b ships natively in MXFP4 quantization, and the upstream
`lmsysorg/sglang:v0.5.12-xeon` image cannot serve it on CPU (MXFP4 is
GPU-gated, sinks attention is unsupported on the CPU backends, and the
published `sgl-kernel` shared library is missing the AVX-512-BF16
compile flags needed for any bf16 matmul).

The SGLang chart ships a one-shot build script that produces a patched
image and imports it directly into k3s containerd. No external registry
is required.

```bash
sudo bash core/helm-charts/sglang/image-build/build-and-import.sh
```

First run takes ~5-10 minutes. Verify:

```bash
sudo k3s ctr images ls | grep enterprise-inference/sglang
# docker.io/enterprise-inference/sglang:v0.5.12-xeon-fix11-debug
```

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

The ApisixRoute has a default 60 s upstream timeout, which is shorter
than CPU inference at ~4 tokens/s can complete. Bump it before sending
real requests:

```bash
kubectl patch apisixroute sglang-gpt-oss-20b-apisixroute --type='json' \
  -p='[{"op":"add","path":"/spec/http/0/timeout","value":{"connect":"5s","read":"600s","send":"600s"}}]'
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

> Lab clusters where `api.example.com` is only in `/etc/hosts` and nginx
> is on a NodePort: add `--resolve api.example.com:30443:127.0.0.1` and
> use `https://api.example.com:30443/...` instead.

If successful, the model returns a chat-completion response with the
answer in `choices[0].message.content` and the model's internal
reasoning in `choices[0].message.reasoning_content`.

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
