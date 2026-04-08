## Bare-Metal RHEL Automation for Enterprise Inference (Intel® Xeon® 6 & Intel® Gaudi® 3)

This guide explains how to use the provided **RHEL-based automation script to prepare a Red Hat Enterprise Linux (RHEL 9)** system and deploy the Enterprise Inference stack on a single-node server.

The script:

- Prepares RHEL for Kubernetes
- Deploys the Enterprise Inference stack
- Supports resume and clean uninstall

---

## 1. Mount RHEL ISO (iDRAC Redfish)

**Script:** [iac/mount-iso.sh](../../ubuntu-22.04/iac/mount-iso.sh)

Mounts the **RHEL 9.6 ISO** via the **iDRAC Redfish Virtual Media API**. Idempotent — skips if already mounted.

> **Note:** The scripts for Sections 1 and 2 are located in the `third_party/Dell/ubuntu-22.04/iac/` folder of this repository. If you have already cloned the Enterprise-Inference repo, navigate to that folder to run them:
> ```bash
> cd third_party/Dell/ubuntu-22.04/iac
> ```

### Required Environment Variables
```bash
export IDRAC_IP=100.67.x.x
export IDRAC_USER=root
export IDRAC_PASS=your-idrac-password
export ISO_URL=https://your-domain.com/rhel-9.6-x86_64-dvd.iso
```

> **Getting the RHEL 9.6 ISO:**
> 1. Log in to the [Red Hat Customer Portal](https://access.redhat.com/downloads) (or sign up for a free [Red Hat Developer Account](https://developers.redhat.com))
> 2. Navigate to **Red Hat Enterprise Linux 9** and download `rhel-9.6-x86_64-dvd.iso`
> 3. Host the ISO on an internal HTTP/HTTPS server reachable by iDRAC
> 4. Set `ISO_URL` to that hosted address

### Mount ISO
```bash
chmod +x mount-iso.sh
./mount-iso.sh
```

---

## 2. Boot RHEL Installer (Terraform + Redfish)

**Script:** [iac/main.tf](../../ubuntu-22.04/iac/main.tf)

Terraform uses the **Dell Redfish provider** to configure a **one-time boot from Virtual Media (CD)** and **force a reboot**.

### Terraform Installation

Install Terraform on your client machine if not already installed: https://developer.hashicorp.com/terraform/install

```bash
terraform version
```

### Terraform Variables

Provide the following in [iac/terraform.tfvars](../../ubuntu-22.04/iac/terraform.tfvars). For all available variables and their defaults, see [iac/variables.tf](../../ubuntu-22.04/iac/variables.tf).

```bash
idrac_endpoint     = "https://100.67.x.x"
idrac_user         = "root"
idrac_password     = "your-idrac-password"
idrac_ssl_insecure = true
```

### Apply Terraform
```bash
terraform init
terraform apply
```

After `terraform apply`, the machine will reboot and the RHEL installer starts automatically from the mounted ISO. Follow the on-screen prompts to complete the OS installation.

---

## 3. System Requirements

| Requirement | Description |
|--------------|-------------|
| **Operating System** | [Red Hat Enterprise Linux 9.6](https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/performing_a_standard_rhel_9_installation/index) |
| **Access** | Root or sudo privileges |
| **Network** | Internet connection for package installation  |
| **Supported Processors** | Intel® Xeon® 6 (CPU deployment) |
| **Optional Accelerator** | Intel® Gaudi® 3 AI Accelerator (for accelerated GPU workloads) |

---

## 4. Enterprise Inference Deployment

Once OS is installed, Download the deploy-enterprise-inference.sh script to your machine using either wget or curl.

**Script:** [iac/deploy-enterprise-inference.sh](./deploy-enterprise-inference.sh)

This script performs **all post-OS configuration** and deploys the **Enterprise Inference stack** on a **single node**.

### Change permission to your file

```bash
chmod +x deploy-enterprise-inference.sh
```

### Run the script

**For Intel® Gaudi® 3:**
```bash
sudo ./deploy-enterprise-inference.sh \
-u user \
-p <your-sudo-password> \
-t hf_xxxxxxxxxxxxx \
-g gaudi3 \
-a cluster-url \
-m "1"
```

**For Intel® Xeon® 6 (CPU):**
```bash
sudo ./deploy-enterprise-inference.sh \
-u user \
-p <your-sudo-password> \
-t hf_xxxxxxxxxxxxx \
-g cpu \
-a cluster-url \
-m "21"
```

**Options & Defaults**

| Option | Required | Default | Description |
|--------|----------|----------|-------------|
| `-u, --username` | Yes (deploy & uninstall) | (none) | Enterprise Inference owner username. Must match the invoking (sudo) user. |
| `-t, --token` | Yes (deploy only) | (none) | Hugging Face access token used to validate and download selected models. |
| `-p, --password` | No | (none) | User sudo password used for Ansible become operations. |
| `-g, --gpu-type` | No | `gaudi3` | Deployment target: `gaudi3` for Intel® Gaudi® 3, `cpu` for Intel® Xeon® 6. |
| `-m, --models` | No | `""` (interactive mode) | Choose model ID from [Pre-Integrated Models List](../../ubuntu-22.04/iac/README.md#pre-integrated-models-list) , based on your deployment type (gaudi or cpu) . If not provided, deployment runs interactively. |
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
-p <your-sudo-password> \
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

Deployment progress is tracked using a local state file: `/tmp/ei-deploy.state`

**What the Deployment Script Does**

- Configures RHEL for Kubernetes (disables swap, sets sysctl, loads kernel modules, disables firewalld)
- Installs required system packages
- Clones the Enterprise-Inference repo
- Updates inference-config.cfg with deployment parameters
- Validates Hugging Face token and model access
- Installs Intel® Gaudi® 3 firmware (if `-g gaudi3`)
- Configures Intel® Xeon® 6 CPU settings (if `-g cpu`)
- Applies kernel/IOMMU tuning (if required)
- Configures SSH keys and sudo access
- Generates self-signed SSL certificates
- Deploys the Enterprise Inference stack (Keycloak or GenAI mode)
- Tracks deployment state and supports resume/uninstall

---

## Verification & Access

After a successful deployment, verify the system at three levels: OS, Enterprise Inference services, and model inference.

### 1. OS & System Validation
Verify the node is healthy and running the expected kernel.
```bash
hostname
uname -r
uptime
```
Expected:
- Correct Hostname
- RHEL 9 kernel (example: 5.14.x-xxx.el9.x86_64)
- System uptime is stable (no reboot loops)

Verify disk and memory
```bash
df -h
free -h
```

### 2. Enterprise Inference Services
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

### 3. Intel® Gaudi® 3 Verification (only if `-g gaudi3`)
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

### 4. Intel® Xeon® 6 Verification (only if `-g cpu`)
Confirm the CPU is recognized and no accelerator-specific drivers are required.
```bash
lscpu | grep -E "Model name|Socket|CPU\(s\)"
```
Expected:
- Intel® Xeon® 6 processor listed
- Socket and CPU count match the hardware specification

### 5. API & Networking Validation
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


### 6. API Health Check
Validate the inference gateway is reachable.
```bash
curl -k https://api.example.com/health
```
Expected:
{"status":"ok"}

---

### 7. Test Model Inference

Refer to the [RedHat9.6 Single-Node Deployment Guide](../EI/single-node/user-guide.md#4-test-the-inference) for instructions on generating a token or API key and testing model inference for both APISIX and GenAI Gateway deployment modes.

---

## Summary

This repository provides a clean, deterministic, enterprise-grade deployment pipeline on RHEL 9.6 supporting both Intel® Xeon® 6 (CPU) and Intel® Gaudi® 3 (accelerated) deployments.