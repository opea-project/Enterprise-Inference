# Intel® AI for Enterprise Inference - Amazon EKS Brownfield Deployment

## Overview

This guide provides specific instructions for deploying Intel AI for Enterprise Inference on **Amazon Elastic Kubernetes Service (EKS)** clusters.

**[← Back to Main Brownfield Guide](brownfield_deployment.md)**

## EKS-Specific Requirements

### Required Components

| Component | Requirement | Notes |
|-----------|-------------|-------|
| **EKS Cluster** | Auto-mode (v1.33) | Validated on Amazon EKS v1.33 |
| **Network Access** | Unrestricted cluster API | Required for deployment automation |
| **kubeconfig** | Admin permissions | Full cluster access needed |
| **Storage** | EBS CSI Driver | Required for persistent volumes (Minimum 250GB for models) |
| **DNS & Certificates** | ACM Certificate | For ALB ingress HTTPS access |
| **ALB Ingress Controller** | Required | aws-load-balancer-controller v1.14.1+ (tested) |
| **AWS Credentials** | Required | AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_DEFAULT_REGION |
| **Proxy Settings** | Corporate proxy config | See [Running behind a corporate proxy](../running-behind-proxy.md) if required |

### EKS Prerequisites

#### 1. ALB Ingress Controller

Ensure the AWS Load Balancer Controller is installed and functional:

**Installation (if needed):**
Follow the official AWS documentation: https://docs.aws.amazon.com/eks/latest/userguide/aws-load-balancer-controller.html

#### 2. EBS CSI Driver

The EBS CSI Driver should be installed and configured as the default StorageClass:

Follow the official AWS documentation: https://docs.aws.amazon.com/eks/latest/userguide/ebs-csi.html

#### 3. AWS Credentials Configuration

Export AWS credentials system-wide by adding them to `/etc/environment`:

```bash
AWS_ACCESS_KEY_ID=your-access-key-id
AWS_SECRET_ACCESS_KEY=your-secret-access-key
AWS_DEFAULT_REGION=your-aws-region
```

After updating, apply the changes:

```bash
source /etc/environment
```

This ensures playbooks running as root can authenticate with AWS.

#### 4. ACM Certificate

Create or import a TLS certificate in AWS Certificate Manager (ACM):
Note the ARN (Amazon Resource Name) of the certificate, You'll need this ARN for the deployment configuration.

### Authentication Requirements

- **AWS Credentials**: Valid AWS access key and secret key with EKS permissions
- See [main guide](brownfield_deployment.md) for HuggingFace token and kubeconfig requirements

### EKS-Specific Pre-requisites

For general prerequisites (node labels, network connectivity, kubeconfig, etc.), see the [main guide prerequisites section](brownfield_deployment.md#pre-requisities).

**EKS-Specific:**

Create 2 node groups like ng-1 for infra and ng-2 for inference

- **Node group labels**: When using EKS node groups, configure labels during node group creation or apply labels to all nodes:
  - For infrastructure node group(ng-1): Add label `role=infra`, preferred node c7i.4xlarge (3 quantity) 
  - For inference node group(ng-2): Add label `role=inference`, preferred node r8i.32xlarge (1 quantity per model) 

- **DNS entries prepared**
  - DNS record for LiteLLM gateway (points to ALB address)
  - DNS record for Keycloak (points to ALB address)
  - DNS record for GenAI Gateway Trace/Langfuse (points to ALB address)
  - **Important**: These DNS records must be created BEFORE or IMMEDIATELY AFTER the ALB is provisioned

- **EBS storage requirements**
  - Minimum 250GB EBS storage capacity for model PVC
  - At least one EBS-based StorageClass configured as default

## Quick Start Deployment

### Step 1: Prepare Kubeconfig

See [main guide - Prepare Kubeconfig](brownfield_deployment.md#prepare-kubeconfig) for preparing the kubeconfig file to connect to the cluster.

### Step 2: Clone Repository

See [main guide - Clone Repository](brownfield_deployment.md#clone-repository) for repository cloning instructions.

### Step 3: Configure EKS Deployment

See [main guide - Common Configuration Parameters](brownfield_deployment.md#common-configuration-parameters) for detailed configuration instructions.

**EKS-Specific Configuration Notes:**

Edit `inventory/inference-config.cfg` to add `aws_certificate_arn`

- `aws_certificate_arn`: **Required** - Must be a valid ACM certificate ARN

### Step 4: Run Deployment

```bash
# Launch deployment script
./inference-stack-deploy.sh
```

**Menu Navigation:**

Select **Option 4** for Brownfield Deployment, provide your kubeconfig path, and choose:
- **Option 1**: Deploy the complete inference stack on your existing cluster
- **Option 2**: Add, remove, or update models after initial deployment (To be run after Option 1)

### Step 5: Create DNS Records

After the deployment completes, ALB addresses will be provisioned. You **must** create DNS records pointing to these ALBs:

```bash
# Get ALB addresses
kubectl get ingress -A

# Example output:
# NAMESPACE           NAME                HOST                           ADDRESS
# genai-gateway       litellm-gateway     api.example.com                xyz123-123456789.us-east-1.elb.amazonaws.com
# default             keycloak            keycloak.example.com           xyz456-123456789.us-east-1.elb.amazonaws.com
# genai-gateway       langfuse            trace.example.com              xyz789-123456789.us-east-1.elb.amazonaws.com
```

Create CNAME records in your DNS provider:
- `api.example.com` → ALB address for litellm-gateway
- `keycloak.example.com` → ALB address for keycloak (if used)
- `trace.example.com` → ALB address for langfuse (if GenAI gateway deployed)

For accessing deployed models refer [accessing-deployed-models](../accessing-deployed-models.md)

## Troubleshooting

### EKS-Specific Issues

For common issues (kubeconfig not found, connection failed, permission denied, etc.), see the [main guide troubleshooting section](brownfield_deployment.md#troubleshooting).

**EKS-Specific Problems:**

| Issue | Solution |
|-------|----------|
| **ALB not provisioning** | Verify aws-load-balancer-controller is running and has proper IAM permissions |
| **Certificate errors** | Check ACM certificate ARN is correct and certificate is validated |
| **AWS authentication failed** | Verify AWS credentials are set in `/etc/environment` and run `source /etc/environment` |
| **EBS PVC not binding** | Ensure EBS CSI Driver is installed and default StorageClass is EBS-based |
| **Keycloak realm creation failed** | Create DNS record for Keycloak ingress, then re-run automation |
| **LiteLLM model registration failed** | Create DNS record for LiteLLM ingress, then re-run automation |
| **DNS resolution issues** | Verify CNAME records are properly configured and propagated |
| **NRI errors** | Ensure `deploy_nri_balloon_policy=off` is set in inference-config.cfg |

### Verification Commands

```bash
# Check ALB controller
kubectl get deployment -n kube-system aws-load-balancer-controller
kubectl logs -n kube-system deployment/aws-load-balancer-controller

# Check ingress resources
kubectl get ingress -A
kubectl describe ingress <ingress-name> -n <namespace>

# Check storage
kubectl get storageclass
kubectl get pvc -A

# Test ALB connectivity
curl -v https://api.example.com/health
```

## EKS-Specific Limitations

- **NRI balloon policy is not supported** on EKS clusters; must set `deploy_nri_balloon_policy=off`
- **DNS records must be created manually** after ALB provisioning for proper access
- **Keycloak realm creation will fail** if DNS record is not created; re-run automation after DNS setup
- **LiteLLM model registration will fail** if DNS record is not created; re-run automation after DNS setup
- **ALB ingress controller and ACM certificate are required** for external HTTPS access
- **AWS credentials must be configured system-wide** in `/etc/environment` for automation
- **EBS CSI Driver must be installed** and default StorageClass must be EBS-based

For general limitations, see the [main brownfield deployment guide](brownfield_deployment.md#known-limitations).

## Additional Resources

- [AWS Load Balancer Controller Documentation](https://docs.aws.amazon.com/eks/latest/userguide/aws-load-balancer-controller.html)
- [EBS CSI Driver Documentation](https://docs.aws.amazon.com/eks/latest/userguide/ebs-csi.html)
- [ACM Certificate Management](https://docs.aws.amazon.com/acm/latest/userguide/acm-overview.html)
- [EKS Best Practices](https://aws.github.io/aws-eks-best-practices/)
- [Main Brownfield Deployment Guide](brownfield_deployment.md)
