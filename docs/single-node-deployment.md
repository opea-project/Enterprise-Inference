# Single Node Deployment Guide

This guide provides step-by-step instructions to deploy Intel® AI for Enterprise Inference on a single node.

## Prerequisites
Before running the automation, ensure the following requirements are met:

1. Ensure the machine meets all the [System Requirements](./prerequisites.md#system-requirements).
2. Log on to the machine as a **non-root** user with sudo privileges and passwordless SSH. Using `root` or a user with a password may lead to unexpected behavior during deployment. 

## Deployment

### Step 1: Modify the hosts file
For this setup, `api.example.com` will be the DNS used, but this can be replaced with another available domain. Follow the steps below:
To test locally, a fake domain (`api.example.com`) needs to be mapped to to `localhost` in the `/etc/hosts` file.

Run the following command to edit the hosts file:
```bash
sudo nano /etc/hosts
```
Add this line at the end:
```bash
127.0.0.1 api.example.com
```
Save and exit (`CTRL+X`, then `Y` and `Enter`).

### Step 2: Generate a self-signed SSL certificate
Run the following commands to create a self-signed SSL certificate. Change the DNS `api.example.com` if needed.
```bash
mkdir -p ~/certs && cd ~/certs
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes -subj "/CN=api.example.com"
```
This generates:
- `cert.pem`: The self-signed certificate.
- `key.pem`: The private key.

### Step 3: Configure the Automation config file
Clone the Enterprise Inference repo, then copy the single node preset inference config file to the working directory:

```bash
cd ~
git clone https://github.com/opea-project/Enterprise-Inference.git
cd Enterprise-Inference
cp -f docs/examples/single-node/inference-config.cfg core/inference-config.cfg
```

Modify `inference-config.cfg` if needed. Ensure the `cluster_url` field is set to the DNS used, and the certificate and key files are pointed to correctly. The keycloak fields and deployment options can be left unchanged.

### Step 4: Update `hosts.yaml` File
Copy the single node preset hosts config file to the working directory:

```bash
cp -f docs/examples/single-node/hosts.yaml core/inventory/hosts.yaml
```

> **Note** The `ansible_user` field is set to *ubuntu* by default. Change it to the actual username used. 

### Step 5: Run the Automation
Now run the automation using the configured files.
```bash
cd core
chmod +x inference-stack-deploy.sh
```
 Export the Hugging Face token as an environment variable by replacing "Your_Hugging_Face_Token_ID" with actual Hugging Face Token. 
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
Run the command below to deploy Llama 3.1 8B parameter model on Intel® Gaudi®.
```bash
./inference-stack-deploy.sh --models "1" --cpu-or-gpu "gpu" --hugging-face-token $HUGGINGFACE_TOKEN
```

Select Option 1 and confirm the Yes/No prompt.

This will deploy the setup automatically. If any issues are encountered, double-check the prerequisites and configuration files.

### Step 6: Testing Inference
On the node run the following commands to test if Intel® AI for Enterprise Inference is successfully deployed:

```bash
export USER=api-admin
export PASSWORD='changeme!!'
export BASE_URL=https://api.example.com
export KEYCLOAK_REALM=master
export KEYCLOAK_CLIENT_ID=api
export KEYCLOAK_CLIENT_SECRET=$(bash scripts/keycloak-fetch-client-secret.sh api.example.com api-admin 'changeme!!' api | awk -F': ' '/Client secret:/ {print $2}')
export TOKEN=$(curl -k -X POST $BASE_URL/token  -H 'Content-Type: application/x-www-form-urlencoded' -d "grant_type=client_credentials&client_id=${KEYCLOAK_CLIENT_ID}&client_secret=${KEYCLOAK_CLIENT_SECRET}" | jq -r .access_token)
```

To test on CPU only:
```bash
curl -k ${BASE_URL}/Meta-Llama-3.1-8B-Instruct-vllmcpu/v1/completions -X POST -d '{"model": "meta-llama/Meta-Llama-3.1-8B-Instruct", "prompt": "What is Deep Learning?", "max_tokens": 25, "temperature": 0}' -H 'Content-Type: application/json' -H "Authorization: Bearer $TOKEN"
```

To test on Intel® Gaudi® AI Accelerators:
```bash
curl -k ${BASE_URL}/Meta-Llama-3.1-8B-Instruct/v1/completions -X POST -d '{"model": "meta-llama/Meta-Llama-3.1-8B-Instruct", "prompt": "What is Deep Learning?", "max_tokens": 25, "temperature": 0}' -H 'Content-Type: application/json' -H "Authorization: Bearer $TOKEN"
```

## Post-Deployment
With the deployed model on the server, refer to the [post-deployment instructions](./README.md#post-deployment) for options.
