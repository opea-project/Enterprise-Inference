## Step 1: Prerequisites to Deploy gpt-oss-20b Model on Xeon with Keycloak

Ensure the Enterprise Inference stack with Keycloak is already deployed before proceeding.

Edit `core/scripts/generate-token.sh` and set your values before sourcing it:

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

This exports: `BASE_URL`, `KEYCLOAK_CLIENT_ID`, `KEYCLOAK_CLIENT_SECRET`, and `TOKEN`.

## Step 2: Build the Patched SGLang Image

gpt-oss-20b ships natively in MXFP4 quantization, and the upstream `lmsysorg/sglang:v0.5.12-xeon` image cannot serve it on CPU (MXFP4 is GPU-gated, sinks attention is unsupported on the CPU backends, and the published `sgl-kernel` shared library is missing the AVX-512-BF16 compile flags needed for any bf16 matmul).

The SGLang chart ships a one-shot build script that produces a patched image and imports it directly into k3s containerd. No external registry is required.

```bash
sudo bash core/helm-charts/sglang/image-build/build-and-import.sh
```

First run takes ~5-10 minutes. Verify:

```bash
sudo k3s ctr images ls | grep enterprise-inference/sglang
# docker.io/enterprise-inference/sglang:v0.5.12-xeon-fix11-debug
```

For a detailed breakdown of what each patch does, see `core/helm-charts/sglang/README.md` (section: What's Patched).

## Step 3: Deploy gpt-oss-20b Model

The chart ships with a canonical values file for this model at `core/helm-charts/sglang/gpt-oss-20b-values.yaml`.

```bash
helm install sglang-gpt-oss-20b ./core/helm-charts/sglang \
  --values ./core/helm-charts/sglang/gpt-oss-20b-values.yaml \
  --set modelSource="openai/gpt-oss-20b" \
  --set huggingface.token="$HUGGING_FACE_HUB_TOKEN" \
  --set ingress.enabled=true \
  --set ingress.secretName="${BASE_URL}" \
  --set ingress.host="${BASE_URL}" \
  --set oidc.clientId="$KEYCLOAK_CLIENT_ID" \
  --set oidc.clientSecret="$KEYCLOAK_CLIENT_SECRET" \
  --set apisixRoute.enabled=true
```

## Step 4: Verify the Deployment

```bash
kubectl get pods
kubectl get apisixroutes
```

Expected Output:

```
NAME                                          READY   STATUS    RESTARTS
keycloak-0                                    1/1     Running   0
keycloak-postgresql-0                         1/1     Running   0
sglang-gpt-oss-20b-<hash>-<hash>              1/1     Running   0
```

> Note: First pod start takes ~4-5 minutes (downloading ~12 GB of weights from Hugging Face, then dequantizing MXFP4 → bf16 in memory). Subsequent restarts are fast because the cache PVC persists the weights.

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

If successful, the model returns a chat-completion response with the answer in `choices[0].message.content` and the model's internal reasoning in `choices[0].message.reasoning_content`.

### A note on `max_tokens`

gpt-oss uses the Harmony chat format: every response starts in an internal "analysis" channel and only switches to the user-visible "final" channel when reasoning is complete. With small budgets the model spends them all reasoning and the `content` field comes back null:

| `max_tokens` | What you'll see |
| ------------ | --------------- |
| ≤ 100        | `content: null`, reasoning truncated |
| 150          | One short sentence — good for quick verification |
| 300          | Paragraph with light formatting |
| > 400        | Hits documented long-form drift (see troubleshooting) |

## To undeploy the model

```bash
helm uninstall sglang-gpt-oss-20b
kubectl delete pvc -l app.kubernetes.io/instance=sglang-gpt-oss-20b   # frees the cached weights
```

## Parameters

| Parameter                                                          | Description                                                                                       |
| ------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------- |
| `--values ./core/helm-charts/sglang/gpt-oss-20b-values.yaml`      | Canonical values file for this model. Pins the patched image, sets bf16, wires the Harmony reasoning and tool-call parsers, sizes resources. |
| `--set modelSource="openai/gpt-oss-20b"`                           | Defines the target model from **Hugging Face** to deploy.                                         |
| `--set huggingface.token="..."`                                    | Authenticates access to gated or private Hugging Face models. The gpt-oss repo is public, so this is optional but harmless. |
| `--set ingress.enabled=true`                                       | Enables Kubernetes **Ingress** to expose the model service externally.                            |
| `--set ingress.host="${BASE_URL}"`                                 | Public hostname or FQDN for the inference endpoint (maps to your Ingress controller IP).          |
| `--set ingress.secretName="${BASE_URL}"`                           | Kubernetes **TLS Secret** used for HTTPS termination at the ingress layer.                        |
| `--set oidc.clientId="..."`                                        | Keycloak OIDC client ID used for token-based authentication.                                      |
| `--set oidc.clientSecret="..."`                                    | Keycloak OIDC client secret corresponding to the client ID.                                       |
| `--set apisixRoute.enabled=true`                                   | Enables the **APISIX** route for gateway routing and OIDC bearer validation.                      |
