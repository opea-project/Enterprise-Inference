# Standard Prerequisites

Before deploying Intel® AI for Enterprise Inference (Enterprise Inference) using the Standard pattern, ensure you have the essential requirements ready. The Standard pattern creates all infrastructure from scratch, making it ideal for new environments or complete automation.

## Overview

The Standard pattern requires minimal prerequisites since it provisions all infrastructure components automatically. This approach provides complete control and automation but takes longer to deploy.

## Required Prerequisites

### 1. IBM Cloud API Key (ibmcloud_api_key)
**What it is:** Your authentication credential for IBM Cloud  
**How to get it:**
1. Go to [IBM Cloud API Keys](https://cloud.ibm.com/iam/apikeys)
2. Click "Create"
3. Give it a name like "Enterprise-Inference-Key"
4. Copy and save the key securely

**Example value:** `ExAmPlE-API-KEY-abc123def456ghi789`

**Required Permissions:**
Your API key needs permissions for:
- VPC Infrastructure Services
- Resource Groups
- Virtual Server Instances
- Network ACLs and Security Groups

### 2. IBM Cloud CLI Installation
**What it is:** Command-line tool for managing IBM Cloud resources  
**How to install:** Follow the [official IBM Cloud CLI installation guide](https://cloud.ibm.com/docs/cli?topic=cli-getting-started)

**After installation, login with your API key:**
```bash
ibmcloud login --apikey YOUR_API_KEY -r <us-east|us-south|eu-de>
```

### 3. IBM Cloud SSH Key (ssh_key)
**What it is:** Your SSH key for secure access to the virtual machine  
**How to get it:**
```bash
# Generate a new key pair (if you don't have one)
ssh-keygen -t rsa -b 4096 -f ~/.ssh/ibm-inference-key

# Upload the public key to IBM Cloud via CLI
ibmcloud is key-create my-inference-key @~/.ssh/ibm-inference-key.pub
```
**Or upload via UI:** [VPC SSH Keys console](https://cloud.ibm.com/vpc-ext/compute/sshKeys)

**Example values:**
- SSH key name: `my-inference-key`
- Private key location: `~/.ssh/ibm-inference-key`

### 3. SSH Private Key (ssh_private_key)
**What it is:** The private SSH key file content for connecting to your instance  
**How to get it:**
- Use the private key you generated in step 2
- This is the content of your `~/.ssh/ibm-inference-key` file
- Must match the public key uploaded to IBM Cloud

**Example:** Content of your private key file (keep this secure!)

### 4. Region and Zone Selection (ibmcloud_region, instance_zone)
**What you need:** Choose where to deploy your infrastructure  
**How to choose:**

**Available regions with Intel® Gaudi® 3 AI accelerator support:**
- `us-east` (zones: us-east-1, us-east-2, us-east-3)
- `us-south` (zones: us-south-1, us-south-2, us-south-3)
- `eu-de` (zones: eu-de-1, eu-de-2, eu-de-3)

> **Note:** These are the only regions where Intel Gaudi 3 AI accelerator instances are currently available.

**Example values:**
- Region: `us-east`
- Zone: `us-east-3`

### 5. Resource Group (resource_group)
**What it is:** Organizational container for your resources  
**Default:** Uses "Default" resource group if not specified  
**How to create a custom one:**
```bash
# Create a new resource group
ibmcloud resource group-create enterprise-inference-rg

# Verify it was created
ibmcloud resource groups
```
**Example value:** `Default` or `enterprise-inference-rg`

### 6. Hugging Face Token (hugging_face_token)
**What it is:** Access token to download AI models  
**How to get it:**
1. Go to [Hugging Face Tokens](https://huggingface.co/settings/tokens) to generate tokens
3. Create a new token with "Read" permissions
4. Accept the license for your chosen model:
   - [Llama-3.1-8B](https://huggingface.co/meta-llama/Llama-3.1-8B-Instruct)
   - [Llama-3.3-70B](https://huggingface.co/meta-llama/Llama-3.3-70B-Instruct)
   - [Llama-3.1-405B](https://huggingface.co/meta-llama/Llama-3.1-405B-Instruct)

**Example value:** `hf_AbCdEfGhIjKlMnOpQrStUvWxYz1234567890`

> **Note:** In terraform.tfvars, this is referred to as `hf_token`

### 7. Model Selection (models)
**What it is:** Which AI model you want to deploy  

| Model Name | Num Cards | Disk | Model ID |
|------------|-----------|------|----------|
| meta-llama/Llama-3.1-8B-Instruct | 1 | 20GB | 1 |
| meta-llama/Llama-3.3-70B-Instruct | 4 | 150GB | 12 |
| meta-llama/Llama-3.1-405B-Instruct | 8 | 900GB | 11 |

**For CLI deployment:** Use the Model ID as a string value (`"1"`, `"12"`, or `"11"`) in your terraform.tfvars file.  
**For UI deployment:** Select from the dropdown - the values will be mapped automatically.

> **Note:** After deployment is complete, you can SSH into the node to deploy additional models not listed above or undeploy existing models as needed.

## Optional Prerequisites

### 8. Cluster URL (cluster_url)
**What it is:** The domain name for your cluster API endpoint  
**How to configure:**
- **For Development/Testing:** Use `api.example.com` (default)
- **For Production:** Use your custom domain (e.g., `ai.yourcompany.com`)

**Example values:**
- Development: `api.example.com`
- Production: `ai.yourcompany.com`

### 9. Keycloak Admin Credentials

#### keycloak_admin_user
**What it is:** Admin username for Keycloak identity management  
**Default:** `admin`  
**Purpose:** Administrative access to Keycloak console

#### keycloak_admin_password
**What it is:** Admin password for Keycloak identity management   
**Purpose:** Administrative access to Keycloak console

> **Security Note:** Use strong, unique credentials for production deployments!

### 10. TLS Configuration (user_cert, user_key)

**For Development/Testing:** You can skip certificates completely when using the default `api.example.com` cluster URL. The deployment will work without providing actual certificate values.

**For Production:** You need a custom domain and SSL certificate  

**If you want external access in production:**
- **Domain:** `ai.yourcompany.com`
- **Certificate:** Valid SSL certificate in PEM format
- **Private Key:** Certificate's private key in PEM format

**DNS and SSL/TLS Setup:**
For detailed instructions on domain configuration and certificate setup, see: [Production Environment Setup](https://github.com/opea-project/Enterprise-Inference/blob/main/docs/prerequisites.md#production-environment)


### 11. Image (image)
**What it is:** The operating system image for your instance  
**Default:** Automatically selected based on region
**How to specify:** Usually leave empty to use default Ubuntu 22.04 image

**To list available images:**
```bash
ibmcloud is images --visibility public | grep ubuntu
```

### 12. ssh_allowed_cidr
0.0.0.0/0 - This is okay for development, but for production, you should strictly define var.ssh_allowed_cidr to a trusted IP range (e.g., your office or VPN IPs)

## Development/Testing Note

For development or testing environments, you can skip the domain name and TLS certificate requirements. The system will automatically use `api.example.com` as the cluster URL, which works for internal cluster access and testing. However, external access will require port forwarding or SSH tunneling.

## Infrastructure That Will Be Created

The Standard pattern automatically provisions:

### Networking Infrastructure
- **VPC:** New Virtual Private Cloud with optimized configuration
- **Subnet:** Public subnet in your chosen zone
- **Security Group:** Pre-configured with required ports (22, 80, 443)
- **Network ACL:** Default rules for secure access
- **Public Gateway:** For internet access
- **Floating IP:** Public IP for your instance

### Compute Infrastructure
- **VSI Instance:** Intel Gaudi 3 AI accelerator-enabled instance based on your model choice
- **SSH Access:** Configured with your SSH key

### Platform Components
- **Kubernetes:** Single-node cluster optimized for AI workloads
- **Intel® Gaudi® 3 AI accelerator operators:** Hardware management and optimization
- **NGINX Ingress:** Traffic routing and load balancing
- **Model Serving:** vLLM inference server with your selected model
- **Authentication:** Keycloak identity management
- **API Gateway:** APISIX for API management
- **Monitoring:** Observability stack

## Account Requirements Verification

### IBM Cloud Account
- [ ] Account is active and in good standing
- [ ] Billing method is configured
- [ ] No outstanding payment issues
- [ ] Account has sufficient credits or payment method

### Service Authorizations
- [ ] VPC Infrastructure Services enabled
- [ ] Virtual Server Instances service available
- [ ] Resource groups accessible

### Quota and Limits
- [ ] VPC limits allow new VPC creation
- [ ] Floating IP quota available

### Regional Availability
- [ ] Target region supports Intel Gaudi 3 AI accelerator instances
- [ ] Chosen zone has available capacity
- [ ] No maintenance windows in target region

## Pre-Deployment Checklist

### Account Setup
- [ ] IBM Cloud account active
- [ ] API key created and tested
- [ ] SSH key generated and uploaded
- [ ] Region and zone selected

### Planning
- [ ] Model size chosen based on requirements
- [ ] Resource group decided (or using Default)
- [ ] Estimated costs reviewed and approved
- [ ] TLS requirements determined

### Access Tokens
- [ ] Hugging Face account created
- [ ] Model licenses accepted
- [ ] Access token generated and saved
- [ ] Token permissions verified

## Next Steps

Once you have all prerequisites ready:
1. **Start Deployment:** [Standard Deployment Guide](./standard-deployment.md)
3. **Alternative:** Consider [Quickstart Pattern](./quickstart-deployment.md) if you have existing infrastructure

---