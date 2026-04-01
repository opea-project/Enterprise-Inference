# Intel® AI for Enterprise Inference — Red Hat 9.6 Single-Node Deployment Guide

## Table of Contents
- [Overview](#overview)
- [Deployment Modes](#deployment-modes)
- [Prerequisites](#prerequisites)
  - [1. System Requirements](#1-system-requirements)
  - [2. SSH Key Setup](#2-ssh-key-setup)
  - [3. DNS and SSL/TLS Setup](#3-dns-and-ssltls-setup)
  - [4. Hugging Face Token Setup](#4-hugging-face-token-setup)
- [Single Node Deployment Guide](#single-node-deployment-guide)
  - [1. Configure the Setup Files and Environment](#1-configure-the-setup-files-and-environment)
  - [2. Run the Deployment](#2-run-the-deployment)
  - [3. Verify the Deployment](#3-verify-the-deployment)
  - [4. Test the Inference](#4-test-the-inference)
    - [APISIX (Keycloak Auth)](#apisix-keycloak-auth)
    - [GenAI Gateway (LiteLLM)](#genai-gateway-litellm)
- [Troubleshooting](#troubleshooting)
- [Summary](#summary)

---

## Overview
This guide walks you through the setup and deployment of **Intel® AI for Enterprise Inference** on a Red Hat Enterprise Linux 9.6 machine in a **single-node** environment.
It is designed for users who may not be familiar with server configuration or AI inference deployment.

**You'll Learn How To:**

- Prepare your system environment
- Set up SSH, DNS, SSL/TLS, and Hugging Face tokens
- Choose and configure a deployment mode (APISIX or GenAI Gateway)
- Run automated deployment scripts for Xeon and Intel® Gaudi® accelerators
- Deploy and test the inference stack on a single node

---

## Deployment Modes

This guide supports two mutually exclusive deployment modes. Choose one based on your authentication and gateway requirements:

| Feature | **APISIX + Keycloak** | **GenAI Gateway (LiteLLM)** |
|---|---|---|
| **API Gateway** | Apache APISIX | LiteLLM Proxy |
| **Authentication** | Keycloak (OAuth2 / JWT) | LiteLLM Master Key |
| **Observability** | Optional | Enabled by default |
| **Config flag** | `deploy_keycloak_apisix=on` / `deploy_genai_gateway=off` | `deploy_keycloak_apisix=off` / `deploy_genai_gateway=on` |
| **Best for** | Enterprise SSO / multi-tenant access control | Simplified multi-model routing and observability |

---

## Prerequisites
Before starting the deployment, ensure your system meets the following requirements.

### 1. System Requirements

| Requirement | Description |
|---|---|
| **Operating System** | Red Hat Enterprise Linux 9.6 |
| **Access** | Root or sudo privileges |
| **Network** | Internet connection for package installation |
| **Optional Accelerator** | Intel® Gaudi® AI Accelerator hardware (for GPU workloads) |
| **HL-SMI Version (hl)** | ≥ 1.22.2 |
| **Firmware Version (fw)** | 61.3.2-sec-3 |
| **SPI / Preboot Firmware (Gaudi3)** | ≥ 1.19.2-fw-57.2.4-sec-2 |
| **Driver Version** | ≥ 1.22.2-5c9d282 |
| **NIC Driver Version** | ≥ 1.22.2-5c9d282 |
| **Habana Container Runtime** | ≥ 1.22.2-32 |
| **Enterprise Inference Version** | release-1.4.0 or newer |

#### Sudo Setup

Ensure `sudo` preserves `/usr/local/bin` in the PATH. Run the following to verify that `/usr/local/bin` is present in `/etc/sudoers` `secure_path`:

```bash
sudo cat /etc/sudoers | grep secure_path
# Expected output:
# Defaults    secure_path = /sbin:/bin:/usr/sbin:/usr/bin:/usr/local/bin
```

If `/usr/local/bin` is missing, use `sudo visudo` to edit the sudoers file and append it as shown above.

---

### 2. SSH Key Setup
SSH keys are required to allow **Ansible** or automation scripts to connect securely to your nodes.

1. **Generate a new SSH key pair:**
    ```bash
    ssh-keygen -t rsa -b 4096
    ```
    - Press **Enter** to accept defaults.
    - You can provide a custom key name if desired.
    - Leave the passphrase field blank for non-interactive use.

2. **Distribute the public key:**

    Copy the contents of your `id_rsa.pub` file to `authorized_keys`:
    ```bash
    echo "<PUBLIC_KEY_CONTENTS>" >> ~/.ssh/authorized_keys
    ```

3. **Verify access:**

    Test SSH connectivity to confirm the key works:
    ```bash
    chmod 600 <path_to_PRIVATE_KEY>
    ssh -i <path_to_PRIVATE_KEY> <USERNAME>@<IP_ADDRESS>
    ```

---

### 3. DNS and SSL/TLS Setup

1. **Generate a self-signed certificate:**

    Use OpenSSL to generate a temporary certificate for your FQDN:
    ```bash
    mkdir -p ~/certs && cd ~/certs && \
    openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes \
      -subj "/CN=api.example.com" \
      -addext "subjectAltName = DNS:api.example.com, DNS:trace-api.example.com"
    ```

    This generates:
    - `cert.pem` — TLS certificate
    - `key.pem` — private key

    > **Note:**
    > `api.example.com` is used as a placeholder throughout this guide.
    > Replace it with **your own fully qualified domain name (FQDN)** wherever it appears.

2. **Map your domain to a local IP (only if not registered in DNS):**

    If your domain is not registered in DNS, map it manually via `/etc/hosts`:
    ```bash
    hostname -I   # Retrieve the machine's IP address
    sudo nano /etc/hosts
    ```

    Add the following line (replace with your actual IP and FQDN):
    ```
    <YOUR_IP> api.example.com
    ```

    Save and exit: **Ctrl+X → Y → Enter**

    > **Note:** This manual mapping is only required when your FQDN is not resolvable via DNS.
    > If your domain is already managed by a DNS provider, skip this step.

---

### 4. Hugging Face Token Setup
1. Visit [huggingface.co](https://huggingface.co) and log in (or create an account).
2. Go to **Settings → Access Tokens**.
3. Click **New Token**, enter a name, select the appropriate scope, and copy the generated value.
4. Store it securely — you will need it during deployment configuration.

---

## Single Node Deployment Guide
This section explains how to deploy Intel® AI for Enterprise Inference on a single Red Hat Enterprise Linux 9.6 server.

**Additional Prerequisites**
- Red Hat Enterprise Linux 9.6 (Plow)
- Root or sudo access
- Python 3.10+ — see [Red Hat Python installation guide](https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/installing_and_using_dynamic_programming_languages/assembly_installing-and-using-python_installing-and-using-dynamic-programming-languages)
- `pip`
- `libselinux-python3`

---

### 1. Configure the Setup Files and Environment

**Step 1: Modify inference-config.cfg**

If the repository is not yet cloned on the target machine, clone it first. Then open the config file:

```bash
vi Enterprise-Inference/core/inventory/inference-config.cfg
```

> **Note:** Make the following changes for your deployment:
> - Replace `cluster_url` with your FQDN — it must match the domain used during certificate generation.
> - Add your Hugging Face token.
> - Set `cpu_or_gpu` to `"cpu"` for Xeon CPU-only deployments, or `"gaudi3"` for Intel® Gaudi® 3 accelerator deployments.
> - Choose the configuration block below based on your chosen [deployment mode](#deployment-modes).

---

#### Configuration for APISIX + Keycloak Mode

Set `deploy_keycloak_apisix=on` and `deploy_genai_gateway=off`. Provide your Keycloak admin credentials.

```ini
cluster_url=api.example.com          # Replace with your FQDN
cert_file=~/certs/cert.pem
key_file=~/certs/key.pem
keycloak_client_id=my-client-id
keycloak_admin_user=your-keycloak-admin-user
keycloak_admin_password=changeme
hugging_face_token=your_hugging_face_token
hugging_face_token_falcon3=your_hugging_face_token
models=
cpu_or_gpu=gaudi3
vault_pass_code=place-holder-123
deploy_kubernetes_fresh=on
deploy_ingress_controller=on
deploy_keycloak_apisix=on
deploy_genai_gateway=off
deploy_observability=off
deploy_llm_models=on
deploy_ceph=off
deploy_istio=off
uninstall_ceph=off
```

---

#### Configuration for GenAI Gateway (LiteLLM) Mode

Set `deploy_genai_gateway=on` and `deploy_keycloak_apisix=off`. Observability is enabled by default in this mode.

```ini
cluster_url=api.example.com          # Replace with your FQDN
cert_file=~/certs/cert.pem
key_file=~/certs/key.pem
keycloak_client_id=my-client-id
keycloak_admin_user=your-keycloak-admin-user
keycloak_admin_password=changeme
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

---

To support non-interactive execution of `inference-stack-deploy.sh`, create a `.become-passfile` containing your sudo password:

```bash
vi core/inventory/.become-passfile
chmod 600 core/inventory/.become-passfile
```

---

**Step 2: Modify hosts.yaml**

Copy the single-node preset hosts config file to the working directory:
```bash
cp -f docs/examples/single-node/hosts.yaml core/inventory/hosts.yaml
```

Open the file for editing:
```bash
vi core/inventory/hosts.yaml
```

> **Note:**
> - Add `ansible_python_interpreter: /usr/libexec/platform-python` to explicitly set the Python interpreter for RHEL.
> - The `ansible_user` field defaults to `ubuntu` — change it to the actual username on your system.

**Example `hosts.yaml`:**
```yaml
all:
  hosts:
    master1:
      ansible_connection: local
      ansible_user: your-username
      ansible_become: true
      ansible_python_interpreter: /usr/libexec/platform-python
```

---

### 2. Run the Deployment

> **Note:**
> The `--models` argument lets you specify a model by its numeric ID.
> See the [full list of available model IDs](../../../ubuntu-22.04/iac/README.md#pre-integrated-models-list).
> If `--models` is omitted, the installer displays the full model list and prompts you to select interactively.

**Deploy on Intel® Gaudi® 3:**
```bash
cd core
chmod +x inference-stack-deploy.sh
./inference-stack-deploy.sh --models "1" --cpu-or-gpu "gaudi3"
```

**Deploy on CPU (Xeon):**
```bash
cd core
chmod +x inference-stack-deploy.sh
./inference-stack-deploy.sh --models "21" --cpu-or-gpu "cpu"
```

When prompted, choose option **1) Provision Enterprise Inference Cluster** and confirm **Yes** to begin installation.

> **Important:** If using Intel® Gaudi® hardware, ensure firmware and drivers meet the minimum versions listed in [System Requirements](#1-system-requirements) before running this script.

---

### 3. Verify the Deployment

**Check pod status:**
```bash
kubectl get pods -A
```

Expected state:
- All pods in `Running` status
- No `CrashLoopBackOff` or `Pending` pods

**APISIX mode — verify routes:**
```bash
kubectl get apisixroutes -A
```

**GenAI Gateway mode — verify LiteLLM proxy:**
```bash
kubectl get pods -n genai -l app=litellm
```

---

### 4. Test the Inference

#### APISIX (Keycloak Auth)

**Step 1 — Obtain an access token**

Before generating the token, ensure all Keycloak-related values are correctly set in `Enterprise-Inference/core/scripts/generate-token.sh`. These values must match the Keycloak settings in `Enterprise-Inference/core/inventory/inference-config.cfg`.

```bash
cd Enterprise-Inference/core/scripts
chmod +x generate-token.sh
. generate-token.sh
```

**Step 2 — Verify the token**

Confirm the token and base URL are available in your shell:
```bash
echo $BASE_URL
echo $TOKEN
```

A valid token is a long JWT string. If empty, re-check your Keycloak configuration.

**Step 3 — Run a test query**

For Gaudi:
```bash
curl -k https://${BASE_URL}/Llama-3.1-8B-Instruct/v1/completions \
  -X POST \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"model": "meta-llama/Llama-3.1-8B-Instruct", "prompt": "What is Deep Learning?", "max_tokens": 25, "temperature": 0}'
```

For CPU:
```bash
curl -k https://${BASE_URL}/Llama-3.1-8B-Instruct-vllmcpu/v1/completions \
  -X POST \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"model": "meta-llama/Llama-3.1-8B-Instruct", "prompt": "What is Deep Learning?", "max_tokens": 25, "temperature": 0}'
```

---

#### GenAI Gateway (LiteLLM)

Set the base URL and retrieve the master key from the vault file:
```bash
export BASE_URL=https://api.example.com    # Replace with your FQDN
```

> **Note:** The `litellm_master_key` is located in `core/inventory/metadata/vault.yml`.

**Run a test query for Gaudi:**
```bash
curl -k https://${BASE_URL}/v1/completions \
  -X POST \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <litellm_master_key>" \
  -d '{
    "model": "meta-llama/Llama-3.1-8B-Instruct",
    "prompt": "What is Deep Learning?",
    "max_tokens": 25,
    "temperature": 0
  }'
```

**Run a test query for CPU:**
```bash
curl -k https://${BASE_URL}/v1/completions \
  -X POST \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <litellm_master_key>" \
  -d '{
    "model": "meta-llama/Llama-3.1-8B-Instruct",
    "prompt": "What is Deep Learning?",
    "max_tokens": 25,
    "temperature": 0
  }'
```

A successful response will contain a JSON completion from the model.

---

## Troubleshooting

This section documents common deployment and runtime issues observed during Intel® AI for Enterprise Inference setup, along with step-by-step resolutions.

[**Troubleshooting Guide**](./troubleshooting.md)

---

## Summary

**You have successfully:**

- Verified system requirements and prerequisites
- Configured SSH keys, DNS, and TLS certificates
- Generated a Hugging Face access token
- Chosen and configured a deployment mode (APISIX or GenAI Gateway)
- Deployed Intel® AI for Enterprise Inference on a single Red Hat 9.6 node
- Tested a working model inference endpoint
