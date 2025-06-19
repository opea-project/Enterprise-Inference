# Getting Started Example

At this point, it is assumed the node or cluster is deployed with Intel® AI for Enterprise Inference. This example lists out steps to test inference using a deployed model.

## Generate API Token (one time only)
Run the commands below to generate an API token used to access the node or cluster. The `BASE_URL` needs to be set to the domain used in the setup process.

```bash
export USER=api-admin
export PASSWORD='changeme!!'
export BASE_URL=https://api.example.com
export KEYCLOAK_REALM=master
export KEYCLOAK_CLIENT_ID=api
export KEYCLOAK_CLIENT_SECRET=$(bash scripts/keycloak-fetch-client-secret.sh api.example.com api-admin 'changeme!!' api | awk -F': ' '/Client secret:/ {print $2}')
export TOKEN=$(curl -k -X POST $BASE_URL/token  -H 'Content-Type: application/x-www-form-urlencoded' -d "grant_type=client_credentials&client_id=${KEYCLOAK_CLIENT_ID}&client_secret=${KEYCLOAK_CLIENT_SECRET}" | jq -r .access_token)
```

Save the token for later use.

## Set Up Environment
1. Install Python.

2. Install `openai`:
```bash
pip install openai
```

3. Set environment variables:
```bash
export BASE_URL="base_url_or_domain_of_node_or_cluster"
export OPENAI_API_KEY="contents_of_TOKEN"
```

## Run Inference 
Create a script `inference.py` with these contents. Change the model if needed.
```python
from openai import OpenAI
import os
 
client = OpenAI(
    api_key=os.environ["OPENAI_API_KEY"],  # This is the default and can be omitted
    base_url= os.environ["BASE_URL"]
)
 
completion = client.chat.completions.create(
  model="meta-llama/Meta-Llama-3.1-8B-Instruct",
  messages=[
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "Hello!"}
  ])

print(completion.choices[0].message)
```

Run the script:
```bash
python inference.py
```

The model can be customized to any model deployed on the node or cluster. The prompt can be changed in the `messages` argument.

# Next Steps
Congratulations! Now use Intel® AI for Enterprise Inference to power other GenAI applications! 

Return to the [Post Deployment](./README.md#post-deployment) section for additional resources and tasks to try.
