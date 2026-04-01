# BAAI/bge-reranker-base: Post-Deployment Configuration Workflow

> **Scope:** Xeon CPU deployments only (vLLM + LiteLLM/GenAI Gateway backend).
> For Gaudi deployments using TEI, the reranker works out of the box — simply set
> `RERANKER_API_ENDPOINT` in your `.env` to your APISIX route URL and skip this guide.

> **Environment:** Intel Xeon CPU | vLLM backend | LiteLLM GenAI Gateway via APISIX
> **Deployment tool:** `inference-deploy.sh` (Enterprise Inference CLI)
> **Final service:** `bge-reranker-base-cpu-vllm-service.default`
> **Gateway auth:** `Bearer Token`

---

## Step 1: Download the Reranker from HuggingFace via the Deployment CLI

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

## Step 2: First Curl Test — Expect an OpenAI Exception

Before any configuration changes, test the rerank endpoint. **This will likely fail** with an OpenAI-format exception because the model is registered with incorrect defaults by the deployment script.

```bash
# Generate a token first: bash core/scripts/generate-token.sh
TOKEN="your-generated-token-here"
BASE_URL="https://api.example.com"

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

> If you see this error, proceed to Step 3. The model is reachable but not yet configured correctly.
> If you get a 404 or connection refused, the pod is not running — go back to Step 1.

---

## Step 3: Get the Model ID from the LiteLLM UI

The `model/update` curl command requires the internal LiteLLM model ID (a UUID), not the HuggingFace model name. Find it in the UI:

1. Open the LiteLLM UI → click **Models + Endpoints** in the left sidebar
2. In the model table, locate the row for `BAAI/bge-reranker-base`
3. The **Model ID** column shows a UUID like `77ce7b6e-3f75-4c66-9623-c735d0024e85`
4. Click the row to open the model detail page
5. Switch to the **Raw JSON** tab — the `id` field at the top of `model_info` is your UUID

---

## Step 4: Run the Model Update Curl Command

Replace `<MODEL_UUID>` with the UUID you copied from the UI in Step 3.

```bash
# TOKEN and BASE_URL should be set from Step 2 above
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

## Step 5: Verify Changes in the LiteLLM UI

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

## Step 6: Re-run the Curl — Successful Result

Run the exact same curl from Step 2 (using the same `TOKEN` and `BASE_URL` variables):

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

## Quick Reference: What Each Step Fixes

```
Step 1  → Creates the K8s pod + initial (broken) LiteLLM registration
Step 2  → Proves the model is reachable but not yet usable for reranking
Step 3  → Gets the UUID needed for the targeted update command
Step 4  → Fixes provider, mode, model name, pass-through via curl
Step 5  → Human verification that all fields persisted correctly in the UI
Step 6  → End-to-end proof that reranking is working
```

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Step 2 curl returns 404 | Pod not running | `kubectl get pods -n default \| grep bge-reranker` |
| Step 4 returns 404 on `/model/update` | Wrong UUID | Re-copy from Raw JSON tab in UI |
| Step 4 returns 200 but UI shows no changes | `db_model: false` | Ensure `"db_model": true` in `model_info` |
| LiteLLM Model Name still shows `openai/` prefix | Update didn't persist | Edit manually in UI Edit Model form and save |
| Step 6 still throws OpenAI exception | `mode: rerank` not set | Check Raw JSON tab — re-run Step 4 |
| All relevance scores ~0.5 | vLLM loaded but not inferring | `kubectl logs <pod-name> -n default` |
| `use_in_pass_through` not toggling | UI bug | Set via curl in Step 4 and confirm in Raw JSON |
