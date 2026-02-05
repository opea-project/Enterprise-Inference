## Bare-Metal Ubuntu Automation for Enterprise Inference (CPU & Gaudi3)

This repository provides an **end-to-end, bare-metal automation workflow** to install **Ubuntu 22.04.5**, boot it using **Dell iDRAC Redfish Virtual Media**, and deploy the **Enterprise Inference stack** (CPU or Gaudi3) on a **single-node system**.

The solution cleanly separates:

- OS installation (ISO + Redfish)
- Boot orchestration (Terraform)
- Post-OS configuration and inference deployment

It is designed for repeatable, resumable, and operator-friendly deployments.

---

### 1. Mount Ubuntu ISO (iDRAC Redfish)

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
**Mount ISO**
```bash
chmod +x mount-iso.sh
./mount-iso.sh
```
---

## 2.Boot Ubuntu Installer (Terraform + Redfish)

**Script:** [iac/main.tf](./main.tf)

Terraform uses the **Dell Redfish provider** to configure a **one-time boot from Virtual Media (CD)** and **force a reboot**.

Key Notes
- ISO must already be mounted using mount-iso.sh
- Boot override is set to Once
- Power reset is forced using redfish_power
- Boot mode (UEFI/Legacy) is not configurable on 17G servers

**Terraform Installation (Client Machine)**

> **Note:** Terraform is executed from a client machine (such as your laptop or a jump host), not from the target server or iDRAC.

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

**Key Features**
- Resume / checkpoint support
- Safe to re-run after failure
- CPU or Gaudi3 support
- Automated configuration of:
    - Packages
    - Repo clone + branch checkout
    - Inventory & config files
    - Firmware & kernel tuning (Gaudi3)
    - SSH, sudo, certificates
    - Final inference stack deployment

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
-m "1" \
-a "replace-with-your-dns"
```
 
| Option |	Description | 
| -------| ------------ |
| -u	| OS username |
| -p    | OS userpassword |
| -t	| Hugging Face token |
| -g	| gaudi3 or cpu |
| -m	| Model IDs |
| -b	| Repo branch (default: release-1.4.0) |
| -r	| Resume from last checkpoint |
| -d    | keycloak or genai, by default set to keycloak |
| -o    | off or on, by default observability set to off |
| -a    | Cluster URL/ FQDN |

**Resume After Failure**

The deployment script is resume-safe. If a failure occurs, simply rerun the script with the -r flag:
```bash
sudo ./deploy-enterprise-inference.sh \
-u user \
-p Linux123! \
-t hf_XXXXXXXXXXXX \
-g gaudi3 \
-m "1" \
-a "replace-with-your-dns"
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

## Summary

This repository provides a clean, deterministic, enterprise-grade deployment pipeline for:

Bare-metal Ubuntu + Enterprise Inference (CPU/Gaudi3)


