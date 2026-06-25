# Single Node Deployment Guide (Envoy Gateway)

This guide provides step-by-step instructions to deploy Intel® AI for Enterprise
Inference on a single node using Envoy Gateway as the ingress controller.

## Prerequisites

1. [SSH Key Setup](./prerequisites.md#ssh-key-setup)
2. [SSL/TLS Certificate Setup for Development Environment](./prerequisites.md#development-environment)
3. [Hugging Face Token Generation](./prerequisites.md#hugging-face-token-generation)

## Deployment

### Step 1: Configure the Automation Config File

Clone the Enterprise Inference repo and set up the config:

```bash
cd ~
git clone https://github.com/opea-project/Enterprise-Inference.git
cd Enterprise-Inference
cp -f docs/examples/single-node/inference-config.cfg core/inventory/inference-config.cfg
```

Edit `core/inventory/inference-config.cfg` and update the following fields:

| Field | Description | Example |
|---|---|---|
| `cluster_url` | DNS hostname for the cluster | `api.example.com` |
| `cert_file` | Path to TLS certificate | `~/certs/cert.pem` |
| `key_file` | Path to TLS private key | `~/certs/key.pem` |
| `keycloak_client_id` | Keycloak OAuth2 client ID | `my-client-id` |
| `keycloak_admin_user` | Keycloak admin username | `your-keycloak-admin-user` |
| `keycloak_admin_password` | Keycloak admin password | `changeme` |

For systems behind a proxy, set the proxy fields accordingly and ensure
`cluster_url` (e.g. `api.example.com`) is included in the `no_proxy` list.

### Step 2: Update `hosts.yaml` File

```bash
cp -f docs/examples/single-node/hosts.yaml core/inventory/hosts.yaml
```

Update the `ansible_user` field to the actual username.

### Step 3: Update `/etc/hosts`

Add the `cluster_url` hostname pointing to the node's IP:

```bash
echo "<NODE_IP> api.example.com" | sudo tee -a /etc/hosts
```

Replace `<NODE_IP>` with the actual node IP address (e.g. `10.75.129.152`).

> **Note:** Do NOT map `cluster_url` to `127.0.0.1`. The Envoy Gateway uses
> `hostPort` bindings which are accessible on the node IP, not loopback.

### Step 4: Run the Automation

```bash
cd core
chmod +x inference-stack-deploy.sh
export HUGGINGFACE_TOKEN=<Your_Hugging_Face_Token>
```

#### CPU Only

```bash
./inference-stack-deploy.sh --models "21" --cpu-or-gpu "cpu" --hugging-face-token $HUGGINGFACE_TOKEN
```

#### Intel® AI Accelerators

```bash
./inference-stack-deploy.sh --models "1" --cpu-or-gpu "gpu" --hugging-face-token $HUGGINGFACE_TOKEN
```

Select Option 1 and confirm the Yes/No prompt.

## Architecture

The traffic flow through the system is:

```
Client (HTTPS:443) → Envoy Gateway → APISIX (auth + rewrite) → vLLM Service
```

- **Envoy Gateway** – Edge proxy, terminates TLS on port 443 (hostPort), routes
  based on path and hostname.
- **APISIX** – Handles authentication (OpenID Connect token introspection via
  Keycloak) and path rewriting.
- **Keycloak** – Identity provider, issues and validates OAuth2 tokens.
- **vLLM** – Model inference backend.

## Testing Inference

### Step 1: Get the Keycloak Client Secret

Retrieve the client secret from the deployed Kubernetes secret:

```bash
export CLIENT_SECRET=$(kubectl get secret <model-release>-secret -n default \
  -o jsonpath='{.data.client_secret}' | base64 -d)
```

For example, with Llama 3.1 8B on CPU:

```bash
export CLIENT_SECRET=$(kubectl get secret vllm-llama-8b-cpu-secret -n default \
  -o jsonpath='{.data.client_secret}' | base64 -d)
```

### Step 2: Generate an Access Token

Generate a token via the internal Keycloak service. This ensures the token
issuer matches what APISIX expects for introspection.

```bash
export KEYCLOAK_IP=$(kubectl get svc keycloak -n default -o jsonpath='{.spec.clusterIP}')
export KEYCLOAK_CLIENT_ID=my-client-id

export TOKEN=$(curl -s --noproxy '*' \
  -H "Host: keycloak.default.svc.cluster.local" \
  http://${KEYCLOAK_IP}/realms/master/protocol/openid-connect/token \
  -X POST \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d "grant_type=client_credentials&client_id=${KEYCLOAK_CLIENT_ID}&client_secret=${CLIENT_SECRET}" \
  | jq -r .access_token)

echo "Token generated (length: ${#TOKEN})"
```

> **Important:** The token must be generated through Keycloak's internal cluster
> service URL (`keycloak.default.svc.cluster.local`) so the token issuer matches
> the APISIX OIDC introspection endpoint. Generating the token via the external
> URL (`https://api.example.com`) will result in an issuer mismatch and `401`
> errors.

### Step 3: Test Inference

Set the base URL:

```bash
export BASE_URL=api.example.com
```

#### CPU Model (vLLM CPU)

Note: `-vllmcpu` is appended to the model path for CPU deployments.

**Completions:**

```bash
curl -sk https://${BASE_URL}/Llama-3.1-8B-Instruct-vllmcpu/v1/completions \
  -X POST \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "model": "meta-llama/Llama-3.1-8B-Instruct",
    "prompt": "What is Deep Learning?",
    "max_tokens": 50,
    "temperature": 0
  }'
```

**Chat Completions:**

```bash
curl -sk https://${BASE_URL}/Llama-3.1-8B-Instruct-vllmcpu/v1/chat/completions \
  -X POST \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "model": "meta-llama/Llama-3.1-8B-Instruct",
    "messages": [{"role": "user", "content": "What is Deep Learning?"}],
    "max_tokens": 50,
    "temperature": 0
  }'
```

**List Models:**

```bash
curl -sk https://${BASE_URL}/Llama-3.1-8B-Instruct-vllmcpu/v1/models \
  -H "Authorization: Bearer $TOKEN"
```

#### Intel® AI Accelerator Model

```bash
curl -sk https://${BASE_URL}/Llama-3.1-8B-Instruct/v1/completions \
  -X POST \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "model": "meta-llama/Llama-3.1-8B-Instruct",
    "prompt": "What is Deep Learning?",
    "max_tokens": 50,
    "temperature": 0
  }'
```

### List Deployed Routes

To see all available model routes:

```bash
kubectl get apisixroutes -A
kubectl get httproute -A
```

## Troubleshooting

### Token returns `401 Authorization Required`

- Ensure the token was generated via the **internal** Keycloak service, not the
  external URL. The issuer in the JWT (`iss` claim) must be
  `http://keycloak.default.svc.cluster.local/realms/master`.
- Verify the client secret matches: `kubectl get secret <release>-secret -o jsonpath='{.data.client_secret}' | base64 -d`

### Cannot reach `https://api.example.com`

- Verify `/etc/hosts` maps `api.example.com` to the **node IP** (not `127.0.0.1`).
- Ensure `api.example.com` is in the `no_proxy` environment variable.
- Verify the Envoy Gateway pod is running: `kubectl get pods -n envoy-gateway-system`
- Confirm port 443 is accessible: `curl -sk https://api.example.com/ -o /dev/null -w '%{http_code}'`

### vLLM pod stuck at `0/1 Running`

- The model may still be downloading or loading. Check logs:
  `kubectl logs -f <vllm-pod-name>`
- CPU model loading for Llama 3.1 8B can take 20-30 minutes on first deploy
  (downloading ~15GB + CPU weight loading).
- Verify the readiness probe failure count has not hit the threshold:
  `kubectl describe pod <vllm-pod-name>`
