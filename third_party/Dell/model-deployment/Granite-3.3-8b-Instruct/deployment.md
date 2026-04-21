
# Deployed with EI Version-1.3.1

## Step 1: Set Environment Variables

```bash
# Export Hugging Face token
export HUGGING_FACE_HUB_TOKEN="your_token_here"

# Set your base URL and API token
export BASE_HOST="your-cluster-url"

#generate keyclock token
export BASE_URL="https://your-cluster-url"
export KEYCLOAK_CLIENT_ID=api
export KEYCLOAK_CLIENT_SECRET="your keyclock client secret"
export TOKEN=$(curl -k -X POST $BASE_URL/token  -H 'Content-Type: application/x-www-form-urlencoded' -d "grant_type=client_credentials&client_id=${KEYCLOAK_CLIENT_ID}&client_secret=${KEYCLOAK_CLIENT_SECRET}" | jq -r .access_token)
```

## Step 2: Deploy Granite-3.3-8b-Instruct Model

```bash
helm install vllm-granite-3-3-instruct-cpu ./core/helm-charts/vllm \
  --values ./core/helm-charts/vllm/xeon-values.yaml \
  --set LLM_MODEL_ID="ibm-granite/granite-3.3-8b-instruct" \
  --set global.HUGGINGFACEHUB_API_TOKEN="$HUGGING_FACE_HUB_TOKEN" \
  --set ingress.enabled=false \
  --set ingress.host="${BASE_HOST}" \
  --set oidc.client_id="$KEYCLOAK_CLIENT_ID" \
  --set oidc.client_secret="$KEYCLOAK_CLIENT_SECRET" \
  --set apisix.enabled=true \
  --set tensor_parallel_size="1" \
  --set pipeline_parallel_size="1"
```

## Step 3: Test the Deployed Model

```bash
curl -k ${BASE_URL}/granite-3.3-8b-instruct-vllmcpu/v1/completions \
  -X POST \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "model": "ibm-granite/granite-3.3-8b-instruct",
    "prompt": "What is Deep Learning?",
    "max_tokens": 25,
    "temperature": 0
  }'
```

## To undeploy the model

```bash
helm uninstall vllm-granite-3-3-instruct-cpu
```

## Parameters

| Parameter                                                 | Description                                                                                           |
| --------------------------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| `--set LLM_MODEL_ID="ibm-granite/granite-3.3-8b-instruct"`| Defines the target model from **Hugging Face** to deploy.                                             |
| `--set global.HUGGINGFACEHUB_API_TOKEN="..."`             | Authenticates access to gated or private Hugging Face models. Replace with your own secure token.     |
| `--set ingress.enabled=true`                              | Enables Kubernetes **Ingress** to expose the model service externally.                                |
| `--set ingress.host="replace-ingress"`                    | Public hostname or FQDN for the inference endpoint (maps to your Ingress controller IP).              |
| `--set ingress.secretname="replace-secret"`               | Kubernetes **TLS Secret** used for HTTPS termination at the ingress layer.                            |












