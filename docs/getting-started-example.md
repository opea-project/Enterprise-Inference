# Getting Started Example

This example lists out steps to test inference using a deployed model.

## Prerequisites

1. At this point, it is assumed the node or cluster is deployed with Intel® AI for Enterprise Inference on-prem or on a CSP. If not, follow the [deployment guide](./README.md) or refer to all [offerings](http://www.intel.com/content/www/us/en/developer/topic-technology/artificial-intelligence/enterprise-inference.html) to set up a server.  
2. Have a list of deployed models on the node or cluster. To see the list, log on to the node or cluster and follow these instructions:

### Method 1 (If APISIX and Keycloak are deployed): Check APISIX Routes
  This works only if APISIX and Keycloak are deployed. Otherwise, refer to [Method 2](#method-2-run-inference-script) below.
  
  Run this command to see the list of models deployed:
  ```bash
  kubectl get apisixroutes
  ```

### Method 2: Run Inference Script
  a) Run `inference-stack-deploy.sh`:
  ```bash
  ./inference-stack-deploy.sh
  ``` 
  b) Select `Option 3: Update Deployed Inference Cluster` to go into the `Update Existing Cluster` menu. 
  c) Select `Option 2: Manage LLM Models` to go into the `Manage LLM Models` menu. 
  d) Select `Option 3: List Installed Models` to check all deployed models on the node or cluster. 
  e) After the script has finished, scroll up in the terminal to look at the section with "Print Installed Models in Comma Separated Format" to see the list of deployed models. 

  **For servers supporting LiteLLM:** Alternatively, run some [Python code with OpenAI](#optional-for-litellm-only-check-list-of-deployed-models) to get this list of models. This can only be done if the base URL and API key are already acquired.

## Generate API Token (one time only)
Run the commands below to generate an API token used to access the node or cluster. The `BASE_URL` needs to be set to the domain used in the setup process.

```bash
source scripts/generate-token.sh
```

Save the token for later use.

## Set Up Environment
1. Install Python. Ensure the version is compatible.

2. Install `openai`:
```bash
pip install openai
```

3. Set environment variables:
- `BASE_URL` is the HTTPS endpoint of the remote server with the model of choice and `/v1` (i.e. https://api.example.com/<deployed-model-name>/v1). The deployed model name can be found by running `kubectl get apisixroutes` for a list of deployed models. **Note:** If using LiteLLM, the model name and `v1` are not needed. By default, LiteLLM is not used.
- `OPENAI_API_KEY` is the access token or key to access the model(s) on the server.

```bash
export BASE_URL="base_url_or_domain_of_node_or_cluster"
export OPENAI_API_KEY="contents_of_TOKEN"
```

## Run Inference 
Create a script `inference.py` with these contents. Change the model if needed. The commented out code that lists the models will only work if the remote server is deployed with LiteLLM. Otherwise, only the specified model from the `BASE_URL` will be shown. If the SSL certificate is self-signed, an HTTP client is created with input argument `verify=false` to bypass it.

```python
from openai import OpenAI
import os
import httpx

# Create a custom HTTP client with SSL verification disabled and custom headers
http_client = httpx.Client(
    verify=False,
    headers={
        "Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}",
        "Content-Type": "application/json"
    }
)

client = OpenAI(
    base_url=os.environ["BASE_URL"],
    http_client=http_client
)

# For remote servers using LiteLLM only: list out available models from endpoint
#models = client.models.list()
#print("Available models: %s" %models)

# Run inference with model
print("Running inference with selected model:")
completion = client.chat.completions.create(
  model="meta-llama/Llama-3.1-8B-Instruct",
  messages=[
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "Hello"}
  ])

print(completion.choices[0].message)

```

Run the script. The output should be the response to the query.
```bash
python3 inference.py
```

The model can be customized to any model deployed on the node or cluster. The prompt can be changed in the `messages` argument.

# Next Steps
Congratulations! Now use Intel® AI for Enterprise Inference to power other GenAI applications! 

Return to the [Post Deployment](./README.md#post-deployment) section for additional resources and tasks to try.
