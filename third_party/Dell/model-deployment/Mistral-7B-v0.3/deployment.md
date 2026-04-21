
# Deployed with EI Version-1.4

## Step 1: Set Environment Variables

```bash
# Export Hugging Face token
export HUGGING_FACE_HUB_TOKEN="your_token_here"

# Set your base URL and API token
export BASE_HOST="your-cluster-url"

```

## Step 2: Deploy Mistral-7b-Instruct Model

```bash
helm install mistral-7b-v3 ./core/helm-charts/vllm \
  --values ./core/helm-charts/vllm/xeon-values.yaml \
  --set LLM_MODEL_ID="mistralai/Mistral-7B-v0.3" \
  --set global.HUGGINGFACEHUB_API_TOKEN="$HUGGING_FACE_HUB_TOKEN" \
  --set ingress.enabled=false \
  --set ingress.host="$BASE_HOST" \
  --set ingress.secretname="$BASE_HOST"
```

## Step 3: Test the Deployed Model

```bash
curl -k ${BASE_URL}/v1/completions \
  -X POST \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer {API_KEY}" \
  -d '{
    "model": "mistralai/Mistral-7B-v0.3",
    "prompt": "What is Deep Learning?",
    "max_tokens": 25,
    "temperature": 0
 }'
```

## To undeploy the model

```bash
helm uninstall mistral-7b-v3
```
## Parameters

| Parameter                                                 | Description                                                                                           |
| --------------------------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| `--set LLM_MODEL_ID="mistralai/Mistral-7B-v0.3"` | Defines the target model from **Hugging Face** to deploy.                                             |                                            |
| `--set global.HUGGINGFACEHUB_API_TOKEN="..."`             | Authenticates access to gated or private Hugging Face models. Replace with your own secure token.     |
| `--set ingress.enabled=false`                              | Enables Kubernetes **Ingress** to expose the model service externally.                                |
| `--set ingress.host="replace-ingress"`                    | Public hostname or FQDN for the inference endpoint (maps to your Ingress controller IP).              |
| `--set ingress.secretname="replace-secret"`               | Kubernetes **TLS Secret** used for HTTPS termination at the ingress layer.                            |
| `--API_KEY`             | Genai gateway api-key|