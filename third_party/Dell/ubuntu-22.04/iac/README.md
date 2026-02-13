## Bare-Metal Ubuntu Automation for Enterprise Inference (CPU & Gaudi3)

This repository provides an **end-to-end, bare-metal automation workflow** to install **Ubuntu 22.04.5**, boot it using **Dell iDRAC Redfish Virtual Media**, and deploy the **Enterprise Inference stack** (CPU or Gaudi3) on a **single-node system**.

The solution cleanly separates:

- OS installation (ISO + Redfish)
- Boot orchestration (Terraform)
- Post-OS configuration and inference deployment

---

## 0. Create Custom Ubuntu ISO (Optional but Recommended)

**Script:** [custom-iso.sh](./iso/custom-iso.sh)

Before mounting the Ubuntu ISO to iDRAC, you may optionally generate a custom Ubuntu 22.04.5 ISO designed for fully unattended installation.

This enables a zero-touch, fully automated OS installation, eliminating manual input during setup and ensuring consistent, repeatable provisioning.

**Host Your Custom ISO (Recommended for Automation)**

After generating the ISO:

1. Upload it to a web-accessible location (e.g., Firebase Hosting, internal web server, object storage, or any HTTP/HTTPS file server).

2. Ensure the ISO is reachable via a public or internally accessible HTTP/HTTPS URL.

3. Save this URL — it will be required in the next step when mounting the ISO using iDRAC Redfish Virtual Media.

Example:
```bash
https://your-domain.com/ubuntu-22.04.5-custom.iso
```

If you already have a prebuilt ISO hosted and accessible via HTTP/HTTPS, you may skip this step and proceed to Step 1: Mount Ubuntu ISO.

For detailed instructions on building a custom ISO, refer to: [ISO Creation Guide](./iso/README.md)

---

## 1. Mount Ubuntu ISO (iDRAC Redfish)

**Script:** [iac/mount-iso.sh](./mount-iso.sh)

This script mounts or unmounts the **Ubuntu 22.04.5 live server ISO** using the **iDRAC Redfish Virtual Media API**.

- Mount ISO
- Idempotent (skips if already mounted)

**Required Environment Variables**
```bash
export IDRAC_IP=100.67.x.x
export IDRAC_USER=root
export IDRAC_PASS=calvin
```
**Specify Custom ISO URL**

If you created and hosted a custom ISO in above step, pass its HTTP/HTTPS URL using:
```bash
export ISO_URL=https://your-domain.com/ubuntu-22.04.5-custom.iso
```

This should be the URL you generated and hosted in the previous step.

You may also use any internally hosted ISO that is reachable by iDRAC.

> Note: If ISO_URL is not provided, the script will automatically use the default Ubuntu 22.04 Live Server ISO. it will Launch the standard installer and Prompt for manual user input during OS installation.

**Mount ISO**
```bash
chmod +x mount-iso.sh
./mount-iso.sh
```
---

## 2.Boot Ubuntu Installer (Terraform + Redfish)

**Script:** [iac/main.tf](./main.tf)

Terraform uses the **Dell Redfish provider** to configure a **one-time boot from Virtual Media (CD)** and **force a reboot**.

**Terraform Installation (Client Machine)**

Terraform is executed from a client machine (such as your laptop or a jump host), not from the target server or iDRAC.

Install Terraform on the machine where you will run the Terraform commands.

**Download Terraform:**
https://developer.hashicorp.com/terraform/install

Choose the package for your operating system and follow the installation instructions.

**Verify Installation**
```bash
terraform version
```
Terraform should return a version without errors. If Terraform is not found, ensure the installation directory is added to your system PATH.

**Terraform Variables**

The following variables must be explicitly provided in 'terraform.tfvars' for the Ubuntu installer boot workflow to function correctly.

While additional variables exist with default values defined in variables.tf, these credentials and endpoints are mandatory and have no safe defaults.


Example (terraform.tfvars):
```bash
idrac_endpoint     = "https://100.67.x.x"
idrac_user         = "root"
idrac_password     = "calvin"
idrac_ssl_insecure = true
ubuntu_username    = "user"
ubuntu_password    = "password"
```

**Apply Terraform**
```bash
terraform init
terraform apply
```

After terraform apply check you IDRAC console, machine will reboot and Ubuntu installer starts automatically from the mounted ISO.  
It will prompt for the user inputs during the installation, provide your inputs and wait for installation to be completed. 

---

## 3.Post-OS Enterprise Inference Deployment

Once OS is installed, Download the deploy-enterprise-inference.sh script to your machine using either wget or curl.

**Script:** [iac/deploy-enterprise-inference.sh](./deploy-enterprise-inference.sh)

This script performs **all post-OS configuration** and deploys the **Enterprise Inference stack** on a **single node**.

**Change permission to your file**

```bash
chmod +x deploy-enterprise-inference.sh
```
**Required Parameters to run the script**

```bash
sudo ./deploy-enterprise-inference.sh \
-u user \
-p Linux123! \
-t hf_xxxxxxxxxxxxx \
-g gaudi3 \
-a cluster-url \
-m "1" \
```
### Options & Defaults

| Option | Required | Default | Description |
|--------|----------|----------|-------------|
| `-u, --username` | Yes (deploy & uninstall) | (none) | Enterprise Inference owner username. Must match the invoking (sudo) user. |
| `-t, --token` | Yes (deploy only) | (none) | Hugging Face access token used to validate and download selected models. |
| `-p, --password` | No | `Linux123!` | User sudo password used for Ansible become operations. |
| `-g, --gpu-type` | No | `gaudi3` | Deployment target type: `gaudi3` or `cpu`. |
| `-m, --models` | No | `""` (interactive mode) | Choose model ID from [Pre-Integrated Models List](#pre-integrated-models-list) , based on your deployment type (gaudi or cpu) . If not provided, deployment runs interactively. |
| `-b, --branch` | No | `release-1.4.0` | Git branch of the Enterprise-Inference repository to clone. |
| `-f, --firmware-version` | No | `1.22.1` | Gaudi3 firmware version (applies only when `-g gaudi3`). |
| `-d, --deployment-mode` | No | `keycloak` | Deployment mode: `keycloak` (Keycloak + APISIX) or `genai` (GenAI Gateway). |
| `-o, --observability` | No | `off` | Enable observability components: `on` or `off`. |
| `-r, --resume` | No | Auto-detected | Resume deployment from last checkpoint if state file exists. |
| `-s, --state-file` | No | `/tmp/ei-deploy.state` | Custom path for deployment state tracking file. |
| `-a, --api-fqdn` | No | `api.example.com` | API Fully Qualified Domain Name used for `/etc/hosts` and TLS certificate generation. |
| `uninstall` | Yes (for uninstall action) | (none) | Removes deployed Enterprise Inference stack and cleans up state. |


**Resume After Failure**

The deployment script is resume-safe. If a failure occurs, simply rerun the script with the -r flag:
```bash
sudo ./deploy-enterprise-inference.sh \
-u user \
-p Linux123! \
-t hf_XXXXXXXXXXXX \
-g gaudi3 \
-a cluster-url \
-m "1" \
-r
```

**To uninstall this deployment**

Below command will delete pods, uninstalls Enterprise Inference stack and state file

```bash
sudo ./deploy-enterprise-inference.sh -u user uninstall
```

**State is tracked in:**

Deployment progress is tracked using a local state file:
```bash
/tmp/ei-deploy.state
```

**What the Deployment Script Does**

- Installs system packages
- Clones Enterprise-Inference repo
- Applies single-node inventory defaults
- Updates inference-config.cfg
- Installs Gaudi3 firmware (if applicable)
- Applies kernel/IOMMU tuning (kernel 6.8)
- Configures SSH and sudo
- Generates SSL certificates
- Runs inference-stack-deploy.sh

---

## Verification & Access

After a successful deployment, verify the system at three levels: OS, Enterprise Inference services, and model inference.

**1. OS & System Validation**
Verify the node is healthy and running the expected kernel.
```bash
hostname
uname -r
uptime
```
Expected:
- Hostname matches ubuntu_hostname
- 5.15.0-164-generic
- System uptime is stable (no reboot loops)

Verify disk and memory
```bash
df -h
free -h
```

**2. Enterprise Inference Services**
Verify all inference services are running.
```bash
kubectl get pods -A
```
Expected:
- All services in RUNNING state
- No failed systemd units

Check systemd services manually if needed:
```bash
systemctl list-units --type=service | grep -i inference
```

**3. Gaudi3 Verification (Only if -g gaudi3)**
Confirm Gaudi devices and firmware are detected.
```bash
hl-smi
```
Expected:
- All Gaudi devices visible
- Firmware version matches deployment input

Verify kernel modules:
```bash
lsmod | grep habanalabs
```

**4. API & Networking Validation**
Verify hostname resolution:
```bash
cat /etc/hosts | grep api.example.com
```
Expected:
- 127.0.0.1 api.example.com

Verify TLS certificates exist:
```bash
ls -l ~/certs
```

Expected:
- cert.pem
- key.pem


**5. API Health Check**
Validate the inference gateway is reachable.
```bash
curl -k https://api.example.com/health
```
Expected:
{"status":"ok"}

---

**6. Test Model Inference**

if EI is deployed with apisix, follow [Testing EI model with apisix](../EI/single-node/user-guide-apisix.md#5-test-the-inference) for generating token and testing the inference

if EI is deployed with genai, follow [Testing EI model with genai](../EI/single-node/user-guide-genai.md#5-test-the-inference) for generating api-key and testing the inference

---

## Additional Information

### Pre-Integrated Models List

Enterprise Inference provides a set of pre-integrated and validated models optimized for performance and stability. These models can be deployed directly using the Enterprise Inference catalog.

**Pre-Integrated Gaudi Models**

**Model ID**   | **Model**                                  |
----------------|:------------------------------------------:|
1               | meta-llama/Llama-3.1-8B-Instruct           |
2               | meta-llama/Llama-3.1-70B-Instruct          |
3               | meta-llama/Llama-3.1-405B-Instruct         |
4               | meta-llama/Llama-3.3-70B-Instruct          |
5               | meta-llama/Llama-4-Scout-17B-16E-Instruct  |
6               | Qwen/Qwen2.5-32B-Instruct                  |
7               | deepseek-ai/DeepSeek-R1-Distill-Qwen-32B   |
8               | deepseek-ai/DeepSeek-R1-Distill-Llama-8B   |
9               | mistralai/Mixtral-8x7B-Instruct-v0.1       |
10              | mistralai/Mistral-7B-Instruct-v0.3         |
11              | BAAI/bge-base-en-v1.5                      |
12              | BAAI/bge-reranker-base                     |
13              | codellama/CodeLlama-34b-Instruct-hf        |
14              | tiiuae/Falcon3-7B-Instruct                 |

**Pre-Integrated CPU Models**

 **Model ID**   | **Model**                                  |
----------------|:------------------------------------------:|
21               |   meta-llama/Llama-3.1-8B-Instruct  |  
22               |   meta-llama/Llama-3.2-3B-Instruct  |   
23               |   deepseek-ai/DeepSeek-R1-Distill-Llama-8B  |   
24               |   deepseek-ai/DeepSeek-R1-Distill-Qwen-32B  |   
25              |   Qwen/Qwen3-1.7B  |
26              |   Qwen/Qwen3-4B-Instruct-2507 |


### Model Deployment

If an Enterprise Inference cluster is already deployed, you can use the interactive deployment script to manage models, including:

 - Deploying additional models from the Enterprise Inference model catalog
 - Deploying custom models directly from Hugging Face
 - Undeploying existing models from the cluster

Refer to the [Model Deployment guide](./model-deployment.md) and run the interactive inference-stack-deploy.sh script to perform these operations.

## Summary

This repository provides a clean, deterministic, enterprise-grade deployment pipeline for:

Bare-metal Ubuntu + Enterprise Inference (CPU/Gaudi3)
