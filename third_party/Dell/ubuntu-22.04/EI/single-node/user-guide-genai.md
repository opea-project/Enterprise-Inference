# Intel® AI for Enterprise Inference - Ubuntu (Gen AI)

## Table of Contents
- [Overview](#overview)
- [Prerequisites](#prerequisites)
  - [1. System Requirements](#1-system-requirements)
  - [2. SSH Key Setup](#2-ssh-key-setup)
  - [3. DNS and SSL/TLS Setup](#3-dns-and-ssltls-setup)
  - [4. Hugging Face Token Setup](#4-hugging-face-token-setup)
- [Single Node Deployment Guide](#single-node-deployment-guide)
  - [1. Clone the Repository](#1-clone-the-repository)
  - [2. Configure the Setup Files and Environment](#2-configure-the-setup-files-and-environment)
  - [3. Run the Deployment](#3-run-the-deployment)
  - [4. Verify the Deployment](#4-verify-the-deployment)
  - [5. Test the Inference](#5-test-the-inference)
- [Summary](#summary)

---

## Overview
This guide walks you through the setup and deployment of **Intel® AI for Enterprise Inference** in a **single-node** environment.  
It is designed for new users who may not be familiar with server configuration or AI inference deployment.

**You’ll Learn How To:**

- Prepare your system environment
- Set up SSH, DNS, SSL/TLS, and Hugging Face tokens
- Run automated scripts for Intel® Gaudi® accelerators
- Deploy and test the inference stack on a single node  

---

## Prerequisites
Before starting the deployment, ensure your system meets the following requirements.

### 1. System Requirements
  		
| Requirement | Description |
|--------------|-------------|
| **Operating System** | Ubuntu 22.04 LTS |
| **Access** | Root or sudo privileges |
| **Network** | Internet connection for package installation  |
| **Optional Accelerator SW Versions**  |  Intel® Gaudi® AI Accelerator hardware (for GPU workloads)  |
| **HL-SMI Version (hl)**  |  ≥1.21.3  |
| **Firmware Version (fw)**  | 61.0.2.0  |
| **SPI / Preboot Firmware (Gaudi3**)  | ≥1.22.0-fw-61.3.2-sec-3  |
| **Driver Version** |  ≥1.21.3-f063886 |
| **NIC Driver Version**  | ≥1.21.3-94c920f  |
| **Habana Container Runtime** |  ≥ 1.21.3  |
| **Enterprise Inference Version** |	release-1.4.0 or newer |

#### Sudo Setup

Ensure `sudo` preserves `/usr/local/bin` in the PATH. Execute the following to check that /usr/local/bin is in /etc/sudoers `secure_path`:

```bash
$ sudo cat /etc/sudoers | grep secure_path
Defaults    secure_path = /sbin:/bin:/usr/sbin:/usr/bin:/usr/local/bin
```

If you do NOT see `/usr/local/bin`, use `sudo visudo` to edit the sudoers file and append it as you see in the sample output above.

### 2. SSH Key Setup
SSH keys are required to allow **Ansible** or automation scripts to connect securely to your nodes.

1. **Generate a new SSH key pair:**
    ```bash
    ssh-keygen -t rsa -b 4096
    ```

    - Press '**Enter**' to accept defaults.
    - You can name your key if desired.
    - Leave the password field blank.

2. **Distribute the public key:**

    Copy the contents of your `id_rsa.pub` file to authorized_keys:
    ```bash
    echo "<PUBLIC_KEY_CONTENTS>" >> ~/.ssh/authorized_keys
    ```

3. **Verify access:**

    Test SSH connectivity:
    ```bash
    chmod 600 <path_to_PRIVATE_KEY>
    ssh -i <path_to_PRIVATE_KEY> <USERNAME>@<IP_ADDRESS>
    ```
   
### 3. DNS and SSL/TLS Setup

1. **Generate a self-signed certificate:**

    Use OpenSSL to generate a temporary certificate:
    ```bash
    mkdir -p ~/certs && cd ~/certs
    openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes -subj "/CN=api.example.com"
    ```
    This will generate:

    `cert.pem` → certificate
    `key.pem` → private key

  > **Note:**  
  > `api.example.com` is used throughout this guide as a sample.
  > Replace it with **your own fully qualified domain name (FQDN)** wherever it appears.


3. **Map your DNS to your local IP (only if not registered in DNS):**

    If your domain is not registered in DNS, you can map it manually by editing your /etc/hosts file
    ```bash
    hostname -I   # Get your machine's private IP
    sudo nano /etc/hosts
    ```
 
    Add this line:
    ```bash
    127.0.0.1 api.example.com
    ```

    Save and exit with CTRL+X → Y → Enter.

    > **Note:** Replace api.example.com with the URL used to generate certs in above step , and this manual mapping is only required if your machine’s hostname is not resolvable via DNS.
    If your domain is already managed by a DNS provider, skip this step.

### 4. Hugging Face Token Setup
  1. Visit huggingface.com and log in (or create an account).
  2. Go to **Settings → Access** Tokens.
  3. Click “**New Token**”, enter a name, and copy the generated value.
  4. Store it securely — you’ll need it for deployment.

---

## Single Node Deployment Guide
This section explains how to deploy Intel® AI for Enterprise Inference on a single Ubuntu 22.04 server.

### 1. Clone the Repository

```bash
git clone https://github.com/opea-project/Enterprise-Inference.git
cd Enterprise-Inference
git checkout ${RELEASE}
```
> **Note:** Update the RELEASE environment variable to point to the desired Enterprise Inference version(for example: release-1.4.0)

### 2. Configure the Setup Files and Environment

**Update inference-config.cfg**

* Production installations should set your own values
* Add your Hugging Face token
* Set the cpu_or_gpu value to "cpu" for Xeon models and "gaudi3" for Intel Gaudi 3 accelerator models
* Set deploy_genai_gateway to on, and make deploy_keycloak_apisix to off

```bash
vi core/inventory/inference-config.cfg
```

```
cluster_url=api.example.com  # <-- Replace with your own FQDN
cert_file=~/certs/cert.pem
key_file=~/certs/key.pem
keycloak_client_id=api
keycloak_admin_user=api-admin
keycloak_admin_password=changeme!!
hugging_face_token=your_hugging_face_token
hugging_face_token_falcon3=your_hugging_face_token
models=
cpu_or_gpu=gaudi3 
vault_pass_code=place-holder-123
deploy_kubernetes_fresh=on
deploy_ingress_controller=on
deploy_keycloak_apisix=off
deploy_genai_gateway=on
deploy_observability=on
deploy_llm_models=on
deploy_ceph=off
deploy_istio=off
uninstall_ceph=off
```
> **Note:** Replace cluster_url must match the DNS name.

**Update hosts.yaml File**

Copy the single node preset hosts config file to the working directory:
```bash
cp -f docs/examples/single-node/hosts.yaml core/inventory/hosts.yaml
```
> Note: The ansible_user field is set to ubuntu by default. Change it to the actual username used.


### 3. Run the Deployment

> **Note:**
> The `--models` argument selects a model using its **numeric ID**  
> If `--models` is omitted, the installer displays the full model list and prompts you to select a model interactively.

**Run the setup for Gaudi:**

```bash
cd core
chmod +x inference-stack-deploy.sh
./inference-stack-deploy.sh --models "1" --cpu-or-gpu "gaudi3"
```

**Run the setup for CPU:**
```bash
cd core
chmod +x inference-stack-deploy.sh
./inference-stack-deploy.sh --models "21" --cpu-or-gpu "cpu"
```

When prompted, choose option **1) Provision Enterprise Inference Cluster** and confirm **Yes** to start installation.
If using Intel® Gaudi® hardware, make sure firmware and drivers are updated before running this script.


### 4. Verify the Deployment
Verify Pods Status
```bash
kubectl get pods -A
```
Expected States:
- All pods Running
- No CrashLoopBackOff
- No Pending pods

### 5. Test the Inference

```bash
export BASE_URL=https://api.example.com
```
Reference the litellm_master_key file under core/inventory/metadata/vault.yml for master-key

**Run a test query for Gaudi:**
```bash
curl -k ${BASE_URL}/Llama-3.1-8B-Instruct/v1/completions \
  -X POST \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <<master-key>>" \
  -d '{
    "model": "meta-llama/Llama-3.1-8B-Instruct",
    "prompt": "What is Deep Learning?",
    "max_tokens": 25,
    "temperature": 0
  }'
```

**Run a test query for CPU:**
```bash
curl -k ${BASE_URL}/Llama-3.1-8B-Instruct-vllmcpu/v1/completions \
-X POST \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <<master-key>>" \
  -d '{
    "model": "meta-llama/Llama-3.1-8B-Instruct",
    "prompt": "What is Deep Learning?",
    "max_tokens": 25,
    "temperature": 0
  }'
```

If successful, the model will return a completion response.

## Summary

**You’ve successfully:**

- Verified system readiness
- Configured SSH, DNS, and SSL
- Generated your Hugging Face token
- Deployed Intel® AI for Enterprise Inference
- Tested a working model endpoint
