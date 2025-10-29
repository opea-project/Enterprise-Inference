# Standard Deployment Guide

## What is the Standard Pattern?

The Standard pattern creates all infrastructure from scratch, giving you complete control and a fresh environment. It automatically provisions VPC, subnets, security groups, and all networking components needed for Intel® AI for Enterprise Inference (Enterprise Inference). Deployment takes ~45 minutes but requires minimal existing infrastructure.

**Perfect for:**
- Teams starting fresh in IBM Cloud
- Complete infrastructure automation
- Isolated environments
- When you prefer infrastructure-as-code approach

## Deployment Modes

You can deploy using two methods:

- **IBM Cloud Catalog UI** - A visual, guided experience through the IBM Cloud console with form-based configuration and built-in validation. This method is ideal for users who prefer graphical interfaces and step-by-step guidance.

**OR**

- **Terraform CLI** - Command-line deployment using infrastructure-as-code principles. This method provides maximum control, enables automation, and integrates well with CI/CD pipelines for experienced users.

## CLI Deployment

### Step 1: Get the Code

You can get the code in two ways:

#### Option A: Download from IBM Cloud Catalog (Recommended)
1. Go to [IBM Cloud Console](https://cloud.ibm.com)
2. Navigate to "Catalog" → "Community registry"
3. Search for "Intel AI for Enterprise Inference" and click on the tile
4. In the bottom right, click "Review deployment options" (highlighted in yellow in the screenshot below)

![Review Deployment Options](assets/standard/review_deployment_options.png)

5. Click "Work with code" → "Download code"
6. Save the .tar.gz file and extract it:

```bash
# Extract the downloaded file
tar -xzf *-1.0.0.tar.gz
cd third_party/IBM/patterns/standard
```

**OR**

#### Option B: Clone from Repository
```bash
# Alternative: Clone from the OPEA repository
git clone https://github.com/opea-project/Enterprise-Inference.git
cd Enterprise-Inference/third_party/IBM/patterns/standard
```

### Step 2: Configure Variables
Update the existing `terraform.tfvars` file with your values:

```bash
# Edit the configuration file
nano terraform.tfvars
# or use your preferred editor: vim, code, etc.
```

Replace the placeholder values with your actual configuration. If you need help finding these values, refer to the [prerequisites guide](./standard-prerequisites.md):

```hcl
# Required: Authentication
ibmcloud_api_key = "your-api-key-here"
ibmcloud_region = "us-east"

# Required: Instance details
instance_zone = "us-east-3"

# Required: Access
ssh_key = "my-inference-key"
ssh_private_key = file("~/.ssh/ibm-inference-key")

# Required: Organization
resource_group = "Default"  # or your custom resource group

# Required: Model (CLI format: use string value from table below)
models = "2"  # Options: "1" (8B), "12" (70B), or "11" (405B)
hugging_face_token = "hf_your_token_here"

# Required: Deployment Mode Configuration
deployment_mode = "single-node"  # Options: "single-node" or "multi-node"
# For multi-node deployments, specify the number of worker nodes:
# IMPORTANT: Use odd numbers (1, 3, 5, 7) for proper Ceph storage cluster operation
worker_gaudi_count = 3  # Number of Gaudi worker nodes (must be 1, 3, 5, or 7)

# Required: ssh_allowed_cidr
# For Production = Use company network range
# For Development/Testing = 0.0.0.0/0
ssh_allowed_cidr = "0.0.0.0/0"

# Required: GenAI Gateway Authentication
vault_pass_code = ""  # Pass code for GenAI Gateway authentication and encryption/decryption

# Optional: TLS Configuration  
# For Development/Testing: Leave cluster_url as "api.example.com" and keep default certificate values
# For Production: Change cluster_url to your domain and provide actual certificate/key content
cluster_url = "api.example.com"
user_cert = "-----BEGIN CERTIFICATE-----\nYOUR_CERT_HERE\n-----END CERTIFICATE-----"
user_key = "-----BEGIN PRIVATE KEY-----\nYOUR_KEY_HERE\n-----END PRIVATE KEY-----"

```

### Step 3: Deploy
```bash
# Initialize Terraform
terraform init

# Preview what will be created
terraform plan

# Deploy (takes ~45 minutes)
terraform apply -auto-approve

# Save the outputs
terraform output > deployment-info.txt
```

![Terraform Deployment Progress](assets/standard/cli-progress.png)

### Step 4: Verify
```bash
# Get your instance IP
INSTANCE_IP=$(terraform output -raw floating_ip)

# SSH to your instance
ssh -i ~/.ssh/ibm-inference-key ubuntu@$INSTANCE_IP

# Check if everything is running
kubectl get pods -A
```

## UI Deployment

### Step 1: Access the Catalog
1. Log into [IBM Cloud Console](https://cloud.ibm.com)
2. Go to "Catalog" → "Community registry"
3. Search for "Intel AI for Enterprise Inference"
4. Click the tile

### Step 2: Select Standard Variation
1. On the variations page, select "Standard"
2. Click "Add to project" in the bottom right (highlighted in yellow below)

![Add to Project](assets/standard/add_to_project.png)

### Step 3: Configure Project

#### Option A: Create New Project
1. Select "Create new"
2. Fill in the project details:
   - **Name:** Your project name (e.g., "enterprise-inference-project")
   - **Description:** Brief description of your project
   - **Configuration name:** Name for this configuration (e.g., "standard-config")
   - **Region:** Select from dropdown
   - **Resource group:** Select from dropdown

> **Note:** For Intel® Gaudi® 3 AI accelerator deployments, ensure you select a region with Gaudi availability: `us-east`, `us-south`, or `eu-de`

**OR**

#### Option B: Add to Existing Project
1. Select "Add to existing"
2. **Select a project:** Choose from dropdown
3. **Configuration name:** Enter a name for this configuration

After selecting your option, click **"Add"** in the bottom right.

### Step 4: Configure Security & Architecture
You'll be taken to the deployment configuration page. First, in the **Security** section, add your IBM Cloud API key, then click **"Next"**.

On the **Configure architecture** page, edit all required inputs (turn on **Advanced** to access optional inputs). Enter the values from your [Prerequisites Guide](./standard-prerequisites.md): SSH key (must exist in IBM Cloud), SSH private key (paste content), IBM Cloud region, instance zone, cluster_url, model selection, Hugging Face token, resource group, vault pass code, full chain certificate, and certificate key. The Standard pattern creates all infrastructure automatically, so you won't need to specify VPC, subnet, or security group names.

> **Note:** For development/testing, leave cluster URL as `api.example.com` and certificates as default values. Only change cluster URL to your registered domain name for production deployments, and only then provide your actual TLS certificate and private key.

### Step 5: Save and Deploy
1. Click "Save" in the top-right to save your configuration
2. Click "Validate" to check your configuration - you'll see "Validating changes..." and "Generating plan..." which takes 2-3 minutes
3. Once you see "Validation successful", enter a comment and click "Approve" to enable the Deploy button
4. Click "Deploy" in the bottom-right 
5. Monitor "Deploying changes..." progress and click "View logs" to see detailed deployment logs (deployment takes ~45 minutes)

![Deployment Progress](assets/standard/in_progress.png)

6. Once deployment completes, you'll see "Deployment successful" with "Changes deployed successfully" 

![Deployment Successful](assets/standard/deployed_successfully.png)

7. Click on "Changes deployed successfully" (highlighted in yellow) to view deployment details

![Deployment Details](assets/standard/click_for_logs.png)

8. Click on the "Logs" tab to view complete deployment logs

### Step 6: View Deployment Outputs
To view deployment outputs including instance IP and model endpoints:
1. Click **Navigation Menu** (☰) in the top-left
2. Select **Projects**
3. Choose your project from the list
4. Click on **Configurations**
5. Click on your deployment name
6. You'll see all deployment outputs including **floating_ip** and model endpoints in a clean interface

![Output Section](assets/standard/output_section.png)

### Step 7: Access Your Deployment
Once deployment completes:
1. Note the **floating_ip** and **reserved_ip** from the deployment outputs
2. SSH to your instance using the floating IP: `ssh -i ~/.ssh/your-key ubuntu@YOUR_FLOATING_IP`
3. Verify services are running with `kubectl get pods -A`

## Deployment Architecture Options

### Single-Node Deployment
In single-node mode, all components (control plane, workloads, and storage) run on a single Intel® Gaudi® 3 AI accelerator server. This is ideal for:
- Development and testing environments
- Proof of concepts
- Smaller workloads
- Cost-conscious deployments

### Multi-Node Deployment
In multi-node mode, the deployment creates a distributed architecture with:
- **Control Plane Nodes**: 1 or 3 Intel® Xeon® processor nodes for Kubernetes control plane (3 nodes for HA)
- **Worker Nodes**: 1, 3, 5, or 7 Intel® Gaudi® 3 AI accelerator nodes for AI inference workloads
  - Each Gaudi node includes 8 NVMe devices used for Ceph distributed storage
  - **Important**: Must use odd numbers (1, 3, 5, 7) of worker nodes for proper Ceph storage cluster quorum
  - With 3 worker nodes and 8 NVMe devices each, you'll have 24 OSD (Object Storage Daemon) pods

Multi-node deployment is ideal for:
- Production environments requiring high availability
- Large-scale inference workloads
- Distributed storage requirements
- Workload isolation and scaling

## What Gets Created

The Standard pattern automatically provisions:

### Networking Infrastructure
- **VPC:** New Virtual Private Cloud
- **Subnet:** Public subnet in your chosen zone
- **Security Group:** Pre-configured with required ports (22, 80, 443)
- **Public Gateway:** For internet access
- **Floating IP:** Public IP for your instance

### Compute Infrastructure
- **VSI Instance:** Intel Gaudi 3 AI accelerator-enabled instance based on your model choice
- **SSH Access:** Configured with your SSH key

### Platform Components
- **Kubernetes:** Single-node cluster
- **Intel® Gaudi® 3 AI accelerator operators:** Hardware management
- **NGINX Ingress:** Traffic routing
- **Model Serving:** vLLM inference server
- **GenAI Gateway:** Unified API gateway with LiteLLM for model orchestration and Langfuse for tracing
- **Monitoring:** Observability stack

## Next Steps

### Accessing Deployed Model

Once deployment is complete, you can start making inference requests to your deployed model.

#### Example: Inferencing with Llama-3.1-8B

1. **SSH to your instance and verify services:**
```bash
# SSH to your instance
ssh -i ~/.ssh/your-key ubuntu@YOUR_FLOATING_IP

# Check that all services are running
kubectl get pods -A
```

> **Interpretation:**  
> Review the output to ensure all pods have a `STATUS` of `Running` or `Completed`.  
> If you see any pods with `Error`, `CrashLoopBackOff`, or other non-running statuses, some services may not have started correctly and may require troubleshooting.
2. **Obtain the GenAI Gateway API key for LiteLLM:**

There are two ways to get the API key to make inference requests:

**Method 1: Quick Test (Using Master Key)**
```bash
# Navigate to the metadata directory
cd Enterprise-Inference/core/inventory/metadata

# View the vault file to get the master key
cat vault.yml | grep litellm_master_key
# Copy the value shown for litellm_master_key - this is your API key
```

**Method 2: Generate Custom API Keys (Production)**
```bash
# The GenAI Gateway URL is available from deployment outputs
# Access the UI at: https://<your-cluster-url>/ui

# To generate a new API key:
# 1. Navigate to the GenAI Gateway UI
# 2. Click on "API Keys" in the sidebar
# 3. Click "Create New Key"
# 4. Set optional parameters (budget, duration, models)
# 5. Copy the generated key - it won't be shown again
```

3. **Make inference requests:**
```bash
# Using the API key obtained from either method above
curl --location 'https://<cluster-url>/v1/chat/completions' \
--header 'Content-Type: application/json' \
--header 'Authorization: Bearer <master-key>' \
--data '{
    "model": "meta-llama/Llama-3.1-8B-Instruct",
    "messages": [
        {
            "role": "user",
            "content": "Hello!"
        }
    ]
}'
```

**Note:** The model endpoint and model information are available from Terraform outputs:
- `genAI_gateway_url` - The GenAI Gateway UI URL
- `model_endpoint` - The API endpoint for model inference (e.g., `https://<cluster-url>/v1/chat/completions`)
- `model_id` - The deployed model identifier (e.g., `meta-llama/Llama-3.1-8B-Instruct`)

These outputs can be found in:
- Terraform output printed after deployment completion
- Running `terraform output` in the deployment directory
- IBM Cloud Deployable Architecture UI outputs section or logs (if deployed via UI)

#### Complete Model Access Documentation

For detailed instructions on accessing all supported models, authentication setup, and advanced usage patterns, visit:

**[Accessing Deployed Models Guide](https://github.com/opea-project/Enterprise-Inference/blob/main/docs/accessing-deployed-models.md)**


## Cleanup and Troubleshooting

### If Something Goes Wrong

#### For CLI Deployments
If your deployment fails or you encounter issues, you can clean up and start over:

```bash
# Clean up all resources created by this deployment
terraform destroy -auto-approve

# This will remove ALL infrastructure created by Standard pattern:
# - The virtual server instance
# - VPC and all networking components
# - Security groups and network ACLs
# - Public gateway and floating IP
```

> **Warning:** Standard pattern cleanup removes the entire VPC and all associated resources. Make sure you don't have other resources in the same VPC before running destroy.

#### For UI Deployments
To undeploy resources created through the IBM Cloud UI:

1. Click **Navigation Menu** (☰) in the top-left
2. Select **Projects**
3. Choose your project from the list
4. Click on **Configurations** tab
5. Find your deployment in the list
6. Click the **3-dots menu** on the right
7. Select **Undeploy**

![Undeploy via UI](assets/standard/undeploy.png)

> **Warning:** UI undeploy for Standard pattern removes the entire VPC and all associated resources, just like CLI cleanup.

### Starting Over

After cleanup, you can modify your configuration and redeploy:

```bash
# Edit your variables if needed
nano terraform.tfvars

# Deploy again
terraform plan
terraform apply -auto-approve
```

---
