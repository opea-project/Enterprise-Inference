# Quickstart Deployment Guide

## What is the Quickstart Pattern?

The Quickstart pattern is the fastest way to deploy Enterprise Inference when you already have IBM Cloud infrastructure in place. It uses your existing VPC, subnets, and security groups to deploy a complete AI inference stack in <~20> minutes.

**Perfect for:**
- Teams with existing IBM Cloud infrastructure
- Quick prototyping and development
- When you want to minimize setup time

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
3. Search for "Enterprise Inference" and click on the tile
4. In the bottom right, click "Review deployment options" (highlighted in yellow in the screenshot below)

![Review Deployment Options](assets/review-deployment-options.png)

5. Click "Work with code" → "Download code"
6. Save the .tar.gz file and extract it:

```bash
# Extract the downloaded file
tar -xzf enterprise-inference-*.tar.gz
cd ibm-da-tag
cd patterns/quickstart
```

**OR**

#### Option B: Clone from Repository
```bash
# Alternative: Clone from the OPEA repository
git clone https://github.com/opea-project/Enterprise-Inference.git
cd Enterprise-Inference/third_party/patterns/quickstart
```

### Step 2: Configure Variables
Update the existing `terraform.tfvars` file with your values:

```bash
# Edit the configuration file
nano terraform.tfvars
# or use your preferred editor: vim, code, etc.
```

Replace the placeholder values with your actual configuration. If you need help finding these values, refer to the [prerequisites guide](./quickstart-prerequisites.md):

```hcl
# Required: Authentication
ibmcloud_api_key = "your-api-key-here"
ibmcloud_region = "us-east"

# Required: Instance details
instance_name = "my-enterprise-inference"
instance_zone = "us-east-3"

# Required: Existing infrastructure
vpc = "your-vpc-name"
subnet = "your-subnet-name" 
security_group = "your-security-group-name"
public_gateway = "your-public-gateway-name"
resource_group = "Default"

# Required: Access
ssh_key = "my-inference-key"
ssh_private_key = file("~/.ssh/ibm-inference-key")

# Required: Model (CLI format: use string value from table below)
models = "2"  # Options: "1" (8B), "12" (70B), or "11" (405B)
hugging_face_token = "hf_your_token_here"

# Optional: Keycloak Admin Configuration
keycloak_admin_user = "admin"      # Default: "admin"
keycloak_admin_password = "admin"  # Default: "admin" (change for production!)

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

# Deploy (takes <~20> minutes)
terraform apply -auto-approve

# Save the outputs
terraform output > deployment-info.txt
```

![Terraform Deployment Progress](assets/terraform-deployment-progress.png)

### Step 4: Verify
```bash
# Get your instance IP
INSTANCE_IP=$(terraform output -raw instance_public_ip)

# SSH to your instance
ssh -i ~/.ssh/ibm-inference-key ubuntu@$INSTANCE_IP

# Check if everything is running
kubectl get pods -A
```

## UI Deployment

### Step 1: Access the Catalog
1. Log into [IBM Cloud Console](https://cloud.ibm.com)
2. Go to "Catalog" → "Community registry"
3. Search for "Enterprise Inference"
4. Click the tile

### Step 2: Select Quickstart Variation
1. On the variations page, select "QuickStart"
2. Click "Add to project" in the bottom right (highlighted in yellow below)

![Add to Project](assets/add_to_project.png)

### Step 3: Configure Project

#### Option A: Create New Project
1. Select "Create new"
2. Fill in the project details:
   - **Name:** Your project name (e.g., "enterprise-inference-project")
   - **Description:** Brief description of your project
   - **Configuration name:** Name for this configuration (e.g., "quickstart-config")
   - **Region:** Select from dropdown
   - **Resource group:** Select from dropdown

> **Note:** For Gaudi deployments, ensure you select a region with Gaudi availability: `us-east`, `us-south`, or `eu-de`

**OR**

#### Option B: Add to Existing Project
1. Select "Add to existing"
2. **Select a project:** Choose from dropdown
3. **Configuration name:** Enter a name for this configuration

After selecting your option, click **"Add"** in the bottom right.

### Step 4: Configure Security & Architecture
You'll be taken to the deployment configuration page. First, in the **Security** section, add your IBM Cloud API key, then click **"Next"**.

On the **Configure architecture** page, edit all required inputs (turn on **Advanced** to access optional inputs). Enter the values from your [Prerequisites Guide](./quickstart-prerequisites.md): SSH key (must exist in IBM Cloud), SSH private key (paste content), IBM Cloud region, instance zone, cluster_url, model selection, Hugging Face token, instance name, VPC name, security group name, public gateway name, subnet name, resource group, Keycloak admin user, Keycloak admin password, full chain certificate, and certificate key.

> **Note:** For development/testing, leave cluster URL as `api.example.com` and certificates as default values. Only change cluster URL to your registered domain name for production deployments, and only then provide your actual TLS certificate and private key.

### Step 5: Save and Deploy
1. Click "Save" in the top-right to save your configuration
2. Click "Validate" to check your configuration - you'll see "Validating changes..." and "Generating plan..." which takes 2-3 minutes
3. Once you see "Validation successful", enter a comment and click "Approve" to enable the Deploy button
4. Click "Deploy" in the bottom-right 
5. Monitor "Deploying changes..." progress and click "View logs" to see detailed deployment logs (deployment takes ~20 minutes for quickstart variation)

![Deployment Progress](assets/in_progress.png)

6. Once deployment completes, you'll see "Deployment successful" with "Changes deployed successfully" 

![Deployment Successful](assets/deployed_successfully.png)

7. Click on "Changes deployed successfully" (highlighted in yellow) to view deployment details

![Deployment Details](assets/click_for_logs.png)

8. Click on the "Logs" tab to see complete deployment logs. Scroll to the bottom to find the important outputs including your instance IP address

![Apply Complete with Outputs](assets/apply_complete.png)

### Step 6: Access Your Deployment
Once deployment completes:
1. Note the **floating_ip** and **reserved_ip** from the logs output (highlighted in yellow in the screenshot above)
2. SSH to your instance using the floating IP: `ssh -i ~/.ssh/your-key ubuntu@YOUR_FLOATING_IP`
3. Verify services are running with `kubectl get pods -A`

## Next Steps

### Accessing Deployed Model

Once deployment is complete, you can start making inference requests to your deployed model.

#### Example: Inferencing with Llama-3-8B

1. **SSH to your instance and verify services:**
```bash
# SSH to your instance
ssh -i ~/.ssh/your-key ubuntu@YOUR_FLOATING_IP

# Check that all services are running
kubectl get pods -A
```

2. **Obtain Keycloak client secret:**
```bash
# Run the client secret fetch script on your instance
keycloak-fetch-client-secret.sh <cluster-url> <keycloak-username> <keycloak-password> <keycloak-client-id>

# Expected output:
# Logged in successfully
# Client secret: keycloak-client-secret
```

3. **Set up environment variables:**
```bash
# The Keycloak cluster URL configured during deployment
export BASE_URL=https://api.example.com

# Default realm (unless changed during deployment)
export KEYCLOAK_REALM=master

# Client ID configured during deployment in keycloak_client_id field
export KEYCLOAK_CLIENT_ID=<your_keycloak_client_id>

# Client secret obtained from step 2
export KEYCLOAK_CLIENT_SECRET=<your_keycloak_client_secret>
```

4. **Obtain access token:**
```bash
export TOKEN=$(curl -k -X POST $BASE_URL/token \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d "grant_type=client_credentials&client_id=${KEYCLOAK_CLIENT_ID}&client_secret=${KEYCLOAK_CLIENT_SECRET}" \
  | jq -r .access_token)
```

5. **Make inference requests:**
```bash
# Make inference request with the obtained token
curl -k ${BASE_URL}/Llama-3.1-8B-Instruct/v1/completions -X POST -d '{
  "model": "meta-llama/Llama-3.1-8B-Instruct",
  "prompt": "What is Deep Learning?", 
  "max_tokens": 25, 
  "temperature": 0
}' -H 'Content-Type: application/json' -H "Authorization: Bearer $TOKEN"
```

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

# This will remove:
# - The virtual server instance
# - Floating IP assignment
# Note: Your existing VPC, subnet, and security groups remain unchanged
```

#### For UI Deployments
To undeploy resources created through the IBM Cloud UI:

1. Click **Navigation Menu** (☰) in the top-left
2. Select **Projects**
3. Choose your project from the list
4. Click on **Configurations** tab
5. Find your deployment in the list
6. Click the **3-dots menu** on the right
7. Select **Undeploy**

![Undeploy via UI](assets/undeploy.png)

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