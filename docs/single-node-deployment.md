# Single Node Deployment Guide

This guide provides step-by-step instructions to deploy Intel® AI for Enterprise Inference on a single node.

## Prerequisites
Before running the automation, it is recommended to complete all [prerequisites](./prerequisites.md). For a quicker setup, the minimum steps are:
1. [SSH Key Setup](./prerequisites.md#ssh-key-setup)
2. [SSL/TLS Certificate Setup for Development Environment](./prerequisites.md#development-environment)
3. [Hugging Face Token Generation](./prerequisites.md#hugging-face-token-generation)

## Deployment

### Step 1: Configure the Automation config file
Clone the Enterprise Inference repo, then copy the single node preset inference config file to the working directory:
```
cd ~
git clone https://github.com/opea-project/Enterprise-Inference.git
cd Enterprise-Inference
cp -f docs/examples/single-node/inference-config.cfg core/inventory/inference-config.cfg
```

Modify `inference-config.cfg` as needed. Ensure the `cluster_url` field is set to the DNS used, and the paths to the certificate and key files are valid. The keycloak fields and deployment options can be left unchanged. For systems behind a proxy, refer to the [proxy guide](./running-behind-proxy.md).

### Step 2: Update `hosts.yaml` File
Copy the single node preset hosts config file to the working directory:

```bash
cp -f docs/examples/single-node/hosts.yaml core/inventory/hosts.yaml
```

> **Note** The `ansible_user` field is set to *ubuntu* by default. Change it to the actual username used. 

### Step 3: Run the Automation
Now run the automation using the configured files.
```bash
cd core
chmod +x inference-stack-deploy.sh
```

Export the Hugging Face token as an environment variable by replacing "Your_Hugging_Face_Token_ID" with actual Hugging Face Token. Alternatively, set `hugging-face-token` to the token value inside `inference-config.cfg`.
```bash
export HUGGINGFACE_TOKEN=<<Your_Hugging_Face_Token_ID>>
```

Follow the steps below depending on the hardware platform. The `models` argument can be excluded and there will be a prompt to select from a [list of models](./supported-models.md).

#### CPU only
Run the command below to deploy the Llama 3.1 8B parameter model on CPU.
```bash
./inference-stack-deploy.sh --models "21" --cpu-or-gpu "cpu" --hugging-face-token $HUGGINGFACE_TOKEN
```
#### Intel® Gaudi® AI Accelerators

> **📝 Note**: If running on Intel® Gaudi® AI Accelerators, ensure firmware and drivers are up to date using the [automated setup scripts](./gaudi-prerequisites.md#automated-installationupgrade-process) before deployment.

Run the command below to deploy the Llama 3.1 8B parameter model on Intel® Gaudi®. For Gaudi 3, set `cpu-or-gpu` to `gaudi3` instead.
```bash
./inference-stack-deploy.sh --models "1" --cpu-or-gpu "gpu" --hugging-face-token $HUGGINGFACE_TOKEN
```

Select Option 1 and confirm the Yes/No prompt.

This will deploy the setup automatically. If any issues are encountered, double-check the prerequisites and configuration files.

### Step 4: Testing Inference
On the node run the following commands to test if Intel® AI for Enterprise Inference is successfully deployed:

If using Keycloak, generate a token using the script `generate-token.sh`. Ensure the values of the variables match what is set in `inference-config.cfg`. This will also set the environment variables `BASE_URL` and `TOKEN` used in the next step.
```bash
source scripts/generate-token.sh
```

If not using Keycloak, set the environment variable `BASE_URL` to the DNS used in the setup i.e. `api.example.com`.

See the example commands below to test inference with Llama 3.1 8B Instruct. For a list of deployed models, this command can be used (if using Keycloak):
```bash
kubectl get apisixroutes
```

To test on CPU only. Note `vllmcpu` is appended to the URL.
```bash
curl -k https://${BASE_URL}/Llama-3.1-8B-Instruct-vllmcpu/v1/completions -X POST -d '{"model": "meta-llama/Llama-3.1-8B-Instruct", "prompt": "What is Deep Learning?", "max_tokens": 50, "temperature": 0}' -H 'Content-Type: application/json' -H "Authorization: Bearer $TOKEN"
```

To test on Intel® Gaudi® AI Accelerators:
```bash
curl -k https://${BASE_URL}/Llama-3.1-8B-Instruct/v1/completions -X POST -d '{"model": "meta-llama/Llama-3.1-8B-Instruct", "prompt": "What is Deep Learning?", "max_tokens": 50, "temperature": 0}' -H 'Content-Type: application/json' -H "Authorization: Bearer $TOKEN"
```

## Post-Deployment
With the deployed model on the server, refer to the [post-deployment instructions](./README.md#post-deployment) for options.
