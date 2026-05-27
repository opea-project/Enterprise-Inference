# SGLang on Intel Enterprise Inference - Single Node Deployment Guide

This guide provides step-by-step instructions for deploying LLM models using the SGLang server on an existing Intel® AI for Enterprise Inference single-node cluster.

> **IMPORTANT:** Unlike other inference engines in this repository, **SGLang natively supports ONLY Intel® Xeon® Processors (CPU)** in this helm chart implementation. Gaudi (HPU) accelerator support is NOT available for SGLang within this enterprise inference stack. Therefore, SGLang must be deployed using the explicit CPU paths and overrides as shown below.

## Prerequisites
Before running the deployment, ensure you have completed all general [prerequisites](./prerequisites.md), and standard cluster deployments. SGLang deployment is performed via Helm directly and is not yet mapped into the main Ansible playbooks like vLLM.

## Setup Steps

### Step 1: Modify the hosts file
Since we are testing locally, we need to map a testing domain (`api.example.com`) to `localhost` in the `/etc/hosts` file.

Run the following command to edit the hosts file:
```bash
sudo nano /etc/hosts
```
Add this line at the end:
```text
127.0.0.1 api.example.com
```
Save and exit (`CTRL+X`, then `Y` and `Enter`).

### Step 2: Generate a self-signed SSL certificate
Run the following command to create a self-signed SSL certificate that covers api.example.com and trace-api.example.com (used if deploying ingress routes):
```bash
mkdir -p ~/certs && cd ~/certs && \
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes \
  -subj "/CN=api.example.com" \
  -addext "subjectAltName = DNS:api.example.com, DNS:trace-api.example.com"
```
Note: the -addext option requires OpenSSL >= 1.1.1.

### Step 3: Configure the Automation config file
Move the single node preset inference config file to the working directory:

```bash
cd ~/Enterprise-Inference
cp -f docs/examples/single-node/inference-config.cfg core/inventory/inference-config.cfg
```

### Step 4: Modify `inference-config.cfg` and set deploy_llm_models to off

Since automatic LLM deployment via the playbook is supported natively for vLLM but not SGLang, turn off automatic model deployment:

```bash
nano ~/Enterprise-Inference/core/inventory/inference-config.cfg
```
Change `" deploy_llm_models=on "` -> `" deploy_llm_models=off "`

Ensure the `cluster_url` field is set to the DNS used, and the paths to the certificate and key files are valid. The deployment options can be left unchanged.

### Step 5: Update `hosts.yaml` File and run the Setup
Copy the single node preset hosts config file to the working directory:

```bash
cp -f docs/examples/single-node/hosts.yaml core/inventory/hosts.yaml
```

> **Note** The `ansible_user` field is set to *ubuntu* by default. Change it to the actual username.

Export your Hugging Face API token and run the automation deployer:

```bash
export HUGGINGFACE_TOKEN="Your_Hugging_Face_Token_ID"

cd ~/Enterprise-Inference/core
chmod +x inference-stack-deploy.sh

./inference-stack-deploy.sh --cpu-or-gpu "cpu" --hugging-face-token $HUGGINGFACE_TOKEN
```

**Select Option 1 and confirm the Yes/No prompt.**

This will deploy the setup automatically. Once the cluster setup is complete, you can configure your SGLang endpoints.

### Step 6: Configure Authentication (OIDC) via Keycloak

If your cluster has Keycloak deployed for API security, you need to grab the auto-generated Client ID and Secret and configure them in the SGLang chart.

```bash
cd ~/Enterprise-Inference/core/scripts
source generate-token.sh

cd ~/Enterprise-Inference/core/helm-charts/sglang/

echo $KEYCLOAK_CLIENT_ID         # Prints your keycloak client ID
echo $KEYCLOAK_CLIENT_SECRET     # Prints your keycloak client secret
```

Open the `values.yaml` file to configure OIDC:
```bash
nano ~/Enterprise-Inference/core/helm-charts/sglang/values.yaml
```

Update the OIDC block:
```yaml
oidc:
  realm: master
  client_id: "<<replace with your KEYCLOAK_CLIENT_ID>>"       
  client_secret: "<<replace with your KEYCLOAK_CLIENT_SECRET>>"
  discovery: "http://keycloak.default.svc.cluster.local/realms/master/.well-known/openid-configuration"
  introspection_endpoint: "http://keycloak.default.svc.cluster.local/realms/master/protocol/openid-connect/token/introspect"
  use_jwks: true
```

#### Host Configuration
If you depend on APISIX for routing, assure you update the host parameter under `apisixRoute`:
```yaml
apisixRoute:
  enabled: true
  namespace: default
  name: ""
  host: "api.example.com"  # Update this to your configured DNS
```

## Optimized Model List
A list of popular LLMs are optimized and run efficiently on CPU, including the most notable open-source models like Llama series, Qwen series, and DeepSeek series like DeepSeek-R1 and DeepSeek-V3.1-Terminus.

| Model Name | BF16 | W8A8_INT8 | FP8 | AWQ_INT4 |
| --- | --- | --- | --- | --- |
| Llama-3.1-8B | meta-llama/Llama-3.1-8B-Instruct | RedHatAI/Meta-Llama-3.1-8B-Instruct-quantized.w8a8 | RedHatAI/Meta-Llama-3.1-8B-Instruct-FP8 | hugging-quants/Meta-Llama-3.1-8B-Instruct-AWQ-INT4 |
| Llama-3.2-11B-Vision | meta-llama/Llama-3.2-11B-Vision-Instruct | | | |
| Llama-3.2-3B | meta-llama/Llama-3.2-3B-Instruct | RedHatAI/Llama-3.2-3B-quantized.w8a8 | RedHatAI/Llama-3.2-3B-Instruct-FP8 | AMead10/Llama-3.2-3B-Instruct-AWQ |
| Llama-3.3-70B | meta-llama/Llama-3.3-70B-Instruct | CalamitousFelicitousness/Llama-3.3-70B-Instruct-W8A8-INT8 | clowman/Llama-3.3-70B-Instruct-FP8-W128 | lambda/Llama-3.3-70B-Instruct-AWQ-4bit |
| Llama-4-Scout-17B | meta-llama/Llama-4-Scout-17B-16E-Instruct | Quantized with Intel AutoRound | | |
| DeepSeek-R1-0528 | | Conexis/DeepSeek-R1-0528-Channel-INT8 | deepseek-ai/DeepSeek-R1-0528 | QuixiAI/DeepSeek-R1-0528-AWQ |
| Qwen3-235B-A22B-Instruct-2507 | Qwen/Qwen3-235B-A22B-Instruct-2507 | | Qwen/Qwen3-235B-A22B-Instruct-2507-FP8 | QuantTrio/Qwen3-235B-A22B-Instruct-2507-AWQ |
| Qwen3-Omni-30B-A3B-Thinking | Qwen/Qwen3-Omni-30B-A3B-Thinking | | | |
| Qwen3.5-397B-A17B | Qwen/Qwen3.5-397B-A17B | | Qwen/Qwen3.5-397B-A17B-FP8 | |
| Qwen3.5-35B-A3B | Qwen/Qwen3.5-35B-A3B | | Qwen/Qwen3.5-35B-A3B-FP8 | |
| Qwen3.5-2B | Qwen/Qwen3.5-2B | | | |
| gemma-3-12b-it | google/gemma-3-12b-it | | RedHatAI/gemma-3-12b-it-FP8-dynamic | pytorch/gemma-3-12b-it-AWQ-INT4 |

> **Note:** The model identifiers listed in the table above have been verified on 6th Gen Intel® Xeon® P-core platforms.

## Deploying LLMs with SGLang (Xeon Only)

To deploy SGLang, you must pass the `xeon-values.yaml` file so it adopts the CPU-specific resource scaling and parameter logic.

### Example: Deploying Meta Llama-3.2-3B-Instruct
Deploying Llama-3 leveraging CPU execution:
```bash
cd ~/Enterprise-Inference/core/helm-charts/sglang/

helm install sglang-llama3 . \
  -f xeon-values.yaml \
  --set LLM_MODEL_ID="meta-llama/Llama-3.2-3B-Instruct" \
  --set global.HUGGINGFACEHUB_API_TOKEN=$HUGGINGFACE_TOKEN
```

### Example: Deploying Neural-Chat
Deploying Intel's Neural Chat:
```bash
helm install sglang-neural-chat . \
  -f xeon-values.yaml \
  --set LLM_MODEL_ID="Intel/neural-chat-7b-v3-3" \
  --set global.HUGGINGFACEHUB_API_TOKEN=$HUGGINGFACE_TOKEN
```

**Note:** Since models are pulled remotely (unless attached to a host path / PVC), the deployment may take several minutes to download depending on the model's weight topology. 

Verify the deployment pods are running:
```bash
kubectl get pods -l app.kubernetes.io/instance=sglang-llama3
```

## Accessing the Deployed Models

First, obtain a Bearer token:
```bash
cd ~/Enterprise-Inference/core/scripts
source generate-token.sh
cd -

export CLIENTID=$KEYCLOAK_CLIENT_ID 
export CLIENT_SECRET=$KEYCLOAK_CLIENT_SECRET
export BASE_URL=https://api.example.com
export TOKEN_URL=${BASE_URL}/token
export TOKEN=$(curl -k -X POST ${TOKEN_URL} -H 'Content-Type: application/x-www-form-urlencoded' -d "grant_type=client_credentials&client_id=${CLIENTID}&client_secret=${CLIENT_SECRET}" | jq -r .access_token)

echo "Access Token: $TOKEN"
```

### Test via External URL (Chat Completions)

SGLang provides an OpenAI-compatible API Server endpoint layout. You can interact with it precisely the same as standard APIs.

```bash
# Inferencing with Llama-3.2-3B
curl -k ${BASE_URL}/llama-3/v1/chat/completions \
  -X POST \
  -d '{"messages": [{"role": "system","content": "You are a helpful AI assistant."},{"role": "user","content": "What is AI inference?"}],"model": "llama-3","max_tokens": 64,"temperature": 0.5}' \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $TOKEN" \
  -sS
```

## Undeployment

To completely extract the deployment, run Helm uninstall:

```bash
# Uninstall the Helm release
helm uninstall sglang-llama3
helm uninstall sglang-neural-chat

# Verify removal
helm list | grep sglang
kubectl get pods | grep sglang
```
