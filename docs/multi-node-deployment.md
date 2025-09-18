# Multi Node Deployment Guide

This guide provides step-by-step instructions to deploy Intel® AI for Enterprise Inference on a Multi-Node setup.

---

## Prerequisites

- **Multiple Ubuntu 22.04 Servers:** At least two networked Ubuntu 22.04 machines with SSH access between them.
- **Passwordless SSH:** Ensure passwordless SSH is set up from the main/master node to all worker nodes.
- **Git and Required Tools:** Git, curl, and other tools installed on all nodes.

---

## 1. Clone the Repository

On the master node (and worker nodes if needed):

```sh
git clone https://github.com/opea-project/Enterprise-Inference.git
cd Enterprise-Inference
```

---

## 2. Prepare Host Configuration

Copy the multi-node example config into place:

```sh
cp -f docs/examples/multi-node/inference-config.cfg core/inference-config.cfg
cp -f docs/examples/multi-node/hosts.yaml core/inventory/hosts.yaml
```

Edit `core/inventory/hosts.yaml` to list all node hostnames/IPs under the correct groups. Example:

```yaml
all:
  hosts:
    master-node:
      ansible_host: 10.1.1.1
    worker-node-1:
      ansible_host: 10.1.1.2
    worker-node-2:
      ansible_host: 10.1.1.3
  children:
    master:
      hosts:
        master-node:
    workers:
      hosts:
        worker-node-1:
        worker-node-2:
```

---

## 3. Set Up /etc/hosts and Certificates

### On All Nodes

Add the master node’s IP to `/etc/hosts`:

```sh
sudo nano /etc/hosts
```
Add:
```
<MASTER_NODE_IP> api.example.com
```

Replace `<MASTER_NODE_IP>` with your master node’s IP.

### On the Master Node

Generate a self-signed SSL certificate:

```sh
mkdir -p ~/certs && cd ~/certs
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes -subj "/CN=api.example.com"
```

Distribute `cert.pem` and `key.pem` to worker nodes as needed.

---

## 4. Export Access Token

On the master node, export your HuggingFace token (replace with your actual token):

```sh
export HUGGINGFACE_TOKEN=<<Your_Hugging_Face_Token_ID>>
```

---

## 5. Deploy the Inference Stack

Navigate to the `core` directory:

```sh
cd core
chmod +x inference-stack-deploy.sh
```

### For CPU Only Nodes

```sh
./inference-stack-deploy.sh --models "21" --cpu-or-gpu "cpu" --hugging-face-token $HUGGINGFACE_TOKEN
```

### For Nodes with Gaudi Accelerators

```sh
./inference-stack-deploy.sh --models "1" --cpu-or-gpu "gpu" --hugging-face-token $HUGGINGFACE_TOKEN
```

Follow the interactive prompts as required.

---

## 6. Test the Deployment

Set up test environment variables:

```sh
export USER=api-admin
export PASSWORD=''
export BASE_URL=https://api.example.com
export KEYCLOAK_REALM=master
export KEYCLOAK_CLIENT_ID=api
export KEYCLOAK_CLIENT_SECRET=$(bash scripts/keycloak-fetch-client-secret.sh api.example.com api-admin 'changeme!!' api | awk -F': ' '/Client secret:/ {print $2}')
export TOKEN=$(curl -k -X POST $BASE_URL/token  -H 'Content-Type: application/x-www-form-urlencoded' -d "grant_type=client_credentials&client_id=${KEYCLOAK_CLIENT_ID}&client_secret=${KEYCLOAK_CLIENT_SECRET}" | jq -r '.access_token')
```

### Example API Call (CPU)

```sh
curl -k ${BASE_URL}/Llama-3.1-8B-Instruct-vllmcpu/v1/completions \
  -X POST \
  -d '{"model": "meta-llama/Llama-3.1-8B-Instruct", "prompt": "What is Deep Learning?", "max_tokens": 25, "temperature":0}' \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json"
```

### Example API Call (GPU)

```sh
curl -k ${BASE_URL}/Llama-3.1-8B-Instruct/v1/completions \
  -X POST \
  -d '{"model": "meta-llama/Llama-3.1-8B-Instruct", "prompt": "What is Deep Learning?", "max_tokens": 25, "temperature":0}' \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json"
```

---

## Notes

- Adjust file and group names in `hosts.yaml` to fit your environment.
- Ensure all nodes are reachable via SSH and have the required ports open.
- For troubleshooting, consult the repository README or open an issue.
