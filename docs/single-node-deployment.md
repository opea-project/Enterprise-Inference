# Single Node Deployment guide

This guide provides step-by-step instructions to deploy Intel® AI for Enterprise Inference on a Single Node.

## Prerequisites
Before running the automation, ensure you have the following:

1. **Ubuntu 22.04 Server**: A machine with Ubuntu 22.04 installed where this automation will run, That's it.

## Setting Up on Ubuntu 22.04
We'll use api.example.com for this setup, follow steps below:

### Step 1: Modify the hosts file
Since we are testing locally, we need to map a fake domain (`api.example.com`) to `localhost` in the `/etc/hosts` file.

Run the following command to edit the hosts file:
```
sudo nano /etc/hosts
```
Add this line at the end:
```
127.0.0.1 api.example.com
```
Save and exit (`CTRL+X`, then `Y` and `Enter`).

### Step 2: Generate a self-signed SSL certificate
Run the following commands to create a self-signed SSL certificate:
```
mkdir -p ~/certs && cd ~/certs
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes -subj "/CN=api.example.com"
```
This generates:
- `cert.pem`: The self-signed certificate.
- `key.pem`: The private key.

### Step 3: Configure the Automation config file
Move the single node preset inference config file to the running directory

```
cd ~
git clone https://github.com/opea-project/Enterprise-Inference.git
cd Enterprise-Inference
cp -f docs/examples/single-node/inference-config.cfg core/inference-config.cfg
```

### Step 4: Update `hosts.yaml` File
Move the single node preset hosts config file to the running directory

>Note : If the name of the current user is not ubuntu, update the ansible_user field in hosts.yaml to the current Linux username.

```
cp -f docs/examples/single-node/hosts.yaml core/inventory/hosts.yaml
```

### Step 5: Run the Automation
Now, you can run the automation using your configured file.
```
cd core
chmod +x inference-stack-deploy.sh
```
 Export your huggingface token as environment variable. Make sure to replace "Your_Hugging_Face_Token_ID" with actual Hugging Face Token. 
```
export HUGGINGFACE_TOKEN=<<Your_Hugging_Face_Token_ID>>
```
If your node is CPU only with no gaudi run below to deploy llama 3.1 8b model.
```
./inference-stack-deploy.sh --models "21" --cpu-or-gpu "cpu" --hugging-face-token $HUGGINGFACE_TOKEN
```
Select option 1 and confirm the Yes/No prompt

If your node has gaudi accelerators run below to deploy llama 3.1 8b model.
```
./inference-stack-deploy.sh --models "1" --cpu-or-gpu "gpu" --hugging-face-token $HUGGINGFACE_TOKEN
```
Select option 1 and confirm the Yes/No prompt

This will deploy the setup automatically. If you encounter any issues, double-check the prerequisites and configuration files.

### Step 6: Testing the Inference
On the Node run the following commands to test the successful deployment of Intel® AI for Enterprise Inference

```
export USER=api-admin
export PASSWORD='changeme!!'
export BASE_URL=https://api.example.com
export KEYCLOAK_REALM=master
export KEYCLOAK_CLIENT_ID=api
export KEYCLOAK_CLIENT_SECRET=$(bash scripts/keycloak-fetch-client-secret.sh api.example.com api-admin 'changeme!!' api | awk -F': ' '/Client secret:/ {print $2}')
export TOKEN=$(curl -k -X POST $BASE_URL/token  -H 'Content-Type: application/x-www-form-urlencoded' -d "grant_type=client_credentials&client_id=${KEYCLOAK_CLIENT_ID}&client_secret=${KEYCLOAK_CLIENT_SECRET}" | jq -r .access_token)
```

To test on CPU only deployment
```
curl -k ${BASE_URL}/Meta-Llama-3.1-8B-Instruct-vllmcpu/v1/completions -X POST -d '{"model": "meta-llama/Meta-Llama-3.1-8B-Instruct", "prompt": "What is Deep Learning?", "max_tokens": 25, "temperature": 0}' -H 'Content-Type: application/json' -H "Authorization: Bearer $TOKEN"
```

To test on GPU only deployment
```
curl -k ${BASE_URL}/Meta-Llama-3.1-8B-Instruct/v1/completions -X POST -d '{"model": "meta-llama/Meta-Llama-3.1-8B-Instruct", "prompt": "What is Deep Learning?", "max_tokens": 25, "temperature": 0}' -H 'Content-Type: application/json' -H "Authorization: Bearer $TOKEN"
```