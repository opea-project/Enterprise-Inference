# BAAI/bge-reranker-base: Post-Deployment Configuration Workflow

> **Deployment tool:** `inference-deploy.sh` (Enterprise Inference CLI)
> **Final service:** `bge-reranker-base-cpu-vllm-service.default`

This guide covers reranker configuration for both deployment types:

| | Keycloak / APISIX | GenAI Gateway (LiteLLM) |
|---|---|---|
| **Backend** | vLLM / TEI (direct) | LiteLLM proxy |
| **Rerank endpoint** | `{BASE_URL}/rerank` | `{BASE_URL}/v1/rerank` |
| **Payload field** | `"texts"` | `"documents"` |
| **Response format** | `[{"index": 0, "score": 0.9}]` | `{"results": [{"index": 0, "relevance_score": 0.9}]}` |
| **Post-deploy config** | None — works out of the box | Steps 3–5 required (LiteLLM model update) |

---

## Step 1: Deploy the Reranker Model

Navigate to the inference directory and run the deployment script:

```bash
cd /Enterprise-Inference
bash ./inference-deploy.sh
```

Follow this menu path:

```
> 3   (Update Deployed Inference Cluster)
> 2   (Manage LLM Models)
> 4   (Deploy Model from Hugging Face)

Enter the HuggingFace Model ID: BAAI/bge-reranker-base
```

> The script will warn that the Kubernetes name will be normalized to `bge-reranker-base` (lowercase, hyphens only). This is expected — proceed.

Wait for the pod to reach `Running` before proceeding:

```bash
kubectl get pods -n default | grep bge-reranker
# bge-reranker-base-cpu-vllm-XXXXX   1/1   Running   0   2m
```

---

## Step 2: Set Up Authentication

Token setup depends on your deployment type:

**Keycloak / APISIX:**
```bash
# Generate a Keycloak client credentials token (expires in 15 minutes)
bash core/scripts/generate-token.sh
# Copy the TOKEN value from the output
TOKEN="your-generated-token-here"

# BASE_URL must include the model route path
BASE_URL="https://api.example.com/bge-reranker-base"
```

**GenAI Gateway (LiteLLM):**
```bash
# Token is the litellm_master_key from core/inventory/metadata/vault.yml
TOKEN="your-vault-token-here"

# BASE_URL is the gateway URL without any model path
BASE_URL="https://api.example.com"
```

---

## Step 3: Curl Test

### Keycloak / APISIX

```bash
curl -k "${BASE_URL}/rerank" \
  -X POST \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${TOKEN}" \
  -d '{
    "model": "BAAI/bge-reranker-base",
    "query": "What is the name of the dataset introduced in this paper?",
    "texts": [
      "The dataset MMHS150K contains 150,000 multimodal tweets.",
      "We use GloVe embeddings for text.",
      "The paper introduces MMHS150K for hate speech detection."
    ],
    "top_n": 3,
    "return_documents": false
  }'
```

**Expected successful response:**
```json
[
  {"index": 2, "score": 0.9273633},
  {"index": 0, "score": 0.9241418},
  {"index": 1, "score": 0.010328152}
]
```

> If this works, you are done — no further configuration needed for Keycloak/APISIX deployments. Set `RERANKER_API_ENDPOINT` in your `.env` to the `BASE_URL` value above and `USE_RERANKING=true`.

### GenAI Gateway (LiteLLM)

```bash
curl -k "${BASE_URL}/v1/rerank" \
  -X POST \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${TOKEN}" \
  -d '{
    "model": "BAAI/bge-reranker-base",
    "query": "What is the name of the dataset introduced in this paper?",
    "documents": [
      "The dataset MMHS150K contains 150,000 multimodal tweets.",
      "We use GloVe embeddings for text.",
      "The paper introduces MMHS150K for hate speech detection."
    ],
    "top_n": 3,
    "return_documents": false
  }'
```

**Expected failure response (OpenAI exception):**
```json
{
  "error": {
    "message": "litellm.BadRequestError: ... This model does not support reranking ...",
    "type": "invalid_request_error",
    "code": 400
  }
}
```

> If you see this error, proceed to Step 4. The model is reachable but not yet configured correctly.
> If you get a 404 or connection refused, the pod is not running — go back to Step 1.

---

## Step 4: Get the Model UUID (GenAI Gateway Only)

> **Skip this step and Steps 5–6 if using Keycloak/APISIX.**

The `model/update` curl command requires the internal LiteLLM model ID (a UUID), not the HuggingFace model name.

**Option A — LiteLLM UI:**

1. Open the LiteLLM UI → click **Models + Endpoints** in the left sidebar
2. In the model table, locate the row for `BAAI/bge-reranker-base`
3. The **Model ID** column shows a UUID like `77ce7b6e-3f75-4c66-9623-c735d0024e85`
4. Click the row to open the model detail page
5. Switch to the **Raw JSON** tab — the `id` field at the top of `model_info` is your UUID

**Option B — Curl (works without UI access):**

```bash
curl -k -s "${BASE_URL}/model/info" \
  -H "Authorization: Bearer ${TOKEN}" | \
  python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f\"{'MODEL NAME':<40} {'API BASE':<50} {'UUID'}\")
print('-' * 110)
for m in data['data']:
    name = m.get('model_name', 'N/A')
    base = m.get('litellm_params', {}).get('api_base', 'N/A')
    uuid = m.get('model_info', {}).get('id', 'N/A')
    print(f'{name:<40} {base:<50} {uuid}')
"
```

---

## Step 5: Run the Model Update Curl Command (GenAI Gateway Only)

Replace `<MODEL_UUID>` with the UUID you copied from Step 4.

```bash
MODEL_UUID="77ce7b6e-3f75-4c66-9623-c735d0024e85"   # ← paste your UUID here

curl -k -X POST "${BASE_URL}/model/update" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${TOKEN}" \
  -d '{
    "model_id": "'"${MODEL_UUID}"'",
    "model_name": "BAAI/bge-reranker-base",
    "litellm_params": {
      "model": "cohere/BAAI/bge-reranker-base",
      "custom_llm_provider": "cohere",
      "api_base": "http://bge-reranker-base-cpu-vllm-service.default",
      "input_cost_per_token": 0.001,
      "output_cost_per_token": 0.002,
      "use_in_pass_through": true,
      "use_litellm_proxy": false,
      "merge_reasoning_content_in_choices": false
    },
    "model_info": {
      "id": "'"${MODEL_UUID}"'",
      "db_model": true,
      "mode": "rerank",
      "input_cost_per_token": 0.001,
      "output_cost_per_token": 0.002,
      "access_via_team_ids": [],
      "direct_access": true,
      "key": "cohere/BAAI/bge-reranker-base"
    }
  }'
```

**Fields being corrected by this command:**

| Field | Before (broken) | After (correct) |
|---|---|---|
| `model` | `openai/BAAI/bge-reranker-base` | `cohere/BAAI/bge-reranker-base` |
| `custom_llm_provider` | `openai` | `cohere` |
| `mode` | *(missing)* | `rerank` |
| `use_in_pass_through` | `false` | `true` |
| `api_base` | *(may include `/v1` suffix)* | `...vllm-service.default` (no `/v1`) |

> Expected response: HTTP 200 with the updated model JSON echoed back.

---

## Step 6: Verify Changes in the LiteLLM UI (GenAI Gateway Only)

After the update curl returns 200, go back to the LiteLLM UI and confirm every field updated correctly.

**Navigation:** Models + Endpoints → click `BAAI/bge-reranker-base` → click **Edit Model**

Verify the following in the Edit Model form:

| Field | Required Value |
|---|---|
| **Public Model Name** | `BAAI/bge-reranker-base` |
| **LiteLLM Model Name** | `cohere/BAAI/bge-reranker-base` |
| **Custom LLM Provider** | `cohere` |
| **API Base** | `http://bge-reranker-base-cpu-vllm-service.default` (no `/v1`) |
| **Use In Pass Through** | `true` (toggled on) |
| **Mode** (in Model Info) | `rerank` |

> The **LiteLLM Model Name** field is the most commonly missed — it must be `cohere/BAAI/bge-reranker-base`, not `BAAI/bge-reranker-base` or `openai/BAAI/bge-reranker-base`. If it did not update, edit it manually here and save.

---

## Step 7: Re-run the Curl — Successful Result (GenAI Gateway Only)

Run the same curl from Step 3 (GenAI Gateway variant):

```bash
curl -k "${BASE_URL}/v1/rerank" \
  -X POST \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${TOKEN}" \
  -d '{
    "model": "BAAI/bge-reranker-base",
    "query": "What is the name of the dataset introduced in this paper?",
    "documents": [
      "The dataset MMHS150K contains 150,000 multimodal tweets.",
      "We use GloVe embeddings for text.",
      "The paper introduces MMHS150K for hate speech detection."
    ],
    "top_n": 3,
    "return_documents": false
  }'
```

**Expected successful response:**

```json
{
  "id": "rerank-...",
  "results": [
    { "index": 2, "relevance_score": 0.9412, "document": { "text": "The paper introduces MMHS150K for hate speech detection." } },
    { "index": 0, "relevance_score": 0.8134, "document": { "text": "The dataset MMHS150K contains 150,000 multimodal tweets." } },
    { "index": 1, "relevance_score": 0.0231, "document": { "text": "We use GloVe embeddings for text." } }
  ],
  "model": "BAAI/bge-reranker-base",
  "usage": { "total_tokens": 87 }
}
```

> Document at index 2 ranks first — it directly answers the query. Document at index 1 (GloVe embeddings) scores near-zero since it is irrelevant. This confirms the reranker is scoring correctly.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Curl returns 404 | Pod not running | `kubectl get pods -n default \| grep bge-reranker` |
| Step 5 returns 404 on `/model/update` | Wrong UUID | Re-copy from Raw JSON tab in UI or re-run Option B curl |
| Step 5 returns 200 but UI shows no changes | `db_model: false` | Ensure `"db_model": true` in `model_info` |
| LiteLLM Model Name still shows `openai/` prefix | Update didn't persist | Edit manually in UI Edit Model form and save |
| Step 7 still throws OpenAI exception | `mode: rerank` not set | Check Raw JSON tab — re-run Step 5 |
| All relevance scores ~0.5 | vLLM loaded but not inferring | `kubectl logs <pod-name> -n default` |
| `use_in_pass_through` not toggling | UI bug | Set via curl in Step 5 and confirm in Raw JSON |
| 401 Unauthorized (Keycloak) | Token expired | Re-run `bash core/scripts/generate-token.sh` |
