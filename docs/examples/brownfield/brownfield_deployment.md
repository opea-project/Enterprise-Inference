# Intel® AI for Enterprise Inference - Brownfield Deployment Guide

## Overview

**Brownfield deployment** enables you to deploy the Intel AI for Enterprise Inference stack on an **existing Kubernetes cluster**. This approach leverages your current infrastructure to deploy Enterprise Inference application stack.

### Use Cases

**Perfect for:**
- Existing Kubernetes clusters (validated with vanilla kubernetes cluster deployed using kubespray)
- Adding AI capabilities to current infrastructure
- Preserving existing workloads and configurations
- Minimizing deployment time and infrastructure costs

**Not suitable for:**
- New cluster setup (use greenfield deployment or fresh installation instead)


## Prerequisites

### Required Components

| Component | Requirement | Notes |
|-----------|-------------|-------|
| **Kubernetes Cluster** | v1.28+ running | Validated on Server version v1.31.4 with kubespray v2.27.0 |
| **Deployment Machine** | Ubuntu 22.04 | Machine running the automation |
| **Network Access** | Unrestricted cluster API | Required for deployment automation |
| **kubeconfig** | Admin permissions | Full cluster access needed |
| **Storage** | Sufficient Capacity | Required for model PVC (Minimum 250GB) and components |
| **DNS & Certificates** | TLS setup | For external LiteLLM gateway access |
| **Proxy Settings** | Corporate proxy config | See [Running behind a corporate proxy](../../running-behind-proxy.md) if required |


### Authentication Requirements

- **HuggingFace Token**: Get from [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens)
- **Kubeconfig**: Admin-level cluster access file with unrestricted access to the cluster.


### Pre-requisities

- **Existing ingress controllers identified and handled**
  - If present, ingress controller must have external access configured (NodePort or LoadBalancer)
  - Ensure ingress controller can route traffic to deployed services
  - Verify ingress class is properly configured and functional

- **Sufficient cluster resources available**
  - Minimum 250GB storage capacity for model PVC
  - Adequate CPU and memory resources for model workloads
  - Check node capacity and available resources before deployment
  - Ensure at least one StorageClass to be present in the Kubernetes cluster.

- **Network connectivity between all nodes verified**
  - All cluster nodes can communicate with each other
  - Nodes have access to container registries and external repositories
  - Firewall rules allow necessary traffic between nodes

- **DNS entries and TLS certificates prepared**
  - Valid DNS record pointing to your cluster ingress endpoint
  - TLS certificate and key files ready for HTTPS access
  - Certificate matches the DNS name configured in inference-config.cfg

- **kubeconfig file tested and working**
  - Kubeconfig has cluster-admin permissions
  - API server endpoint is accessible from deployment machine
  - Successfully tested with `kubectl cluster-info` and `kubectl get nodes`

## Quick Start Deployment

### Step 1: Prepare kubeconfig

The kubeconfig file must be copied from your Kubernetes control plane node to the deployment machine (bastion/client node) where you'll run the brownfield deployment automation.

**Locate kubeconfig on control plane:**

The kubeconfig location varies by cluster type:

- **Kubespray deployments**: `/etc/kubernetes/admin.conf`
- **Other distributions**: Check your cluster documentation to locate the admin kubeconfig file.

**Steps to obtain kubeconfig:**

1. Access your control plane node
2. Locate the admin kubeconfig file (e.g., `/etc/kubernetes/admin.conf` for kubespray)
3. Copy the kubeconfig file to your deployment machine

**Verify kubeconfig works from the bastion or client node after copying from control plane:**

```bash
export KUBECONFIG=/path/to/your/kubeconfig
kubectl cluster-info
kubectl get nodes
```

**Important: Ensure the server IP/hostname in kubeconfig points to the correct Kubernetes API endpoint**


### Step 2: Clone Repository

```bash
cd ~
git clone https://github.com/opea-project/Enterprise-Inference.git
cd Enterprise-Inference/core
chmod +x inference-stack-deploy.sh
```

### Step 3: Configure Deployment

Edit `inventory/inference-config.cfg`:

```properties
# Cluster Configuration
cluster_url=api.example.com                     # Domain name for external access to the inference services
cert_file=~/certs/cert.pem                      # Path to TLS certificate file for HTTPS
key_file=~/certs/key.pem                        # Path to TLS private key file for HTTPS

# Keycloak Authentication (if using Keycloak for auth)
keycloak_client_id=my-client-id                 # Keycloak client ID for application authentication
keycloak_admin_user=your-keycloak-admin-user    # Keycloak admin username
keycloak_admin_password=changeme                # Keycloak admin password (change this!)

# HuggingFace Authentication
hugging_face_token=your_hugging_face_token      # HuggingFace token for model downloads (get from https://huggingface.co/settings/tokens)
hugging_face_token_falcon3=your_hugging_face_token  # Separate token for Falcon3 models (if needed)

# Model Configuration
models=21                                       # Model selection (see supported models list - 21 is example model ID)
cpu_or_gpu=cpu                                  # Hardware accelerator: 'cpu' or 'gpu'

# Deployment Options
deploy_kubernetes_fresh=off                      # Deploy fresh Kubernetes cluster (automation sets 'off' for brownfield)
deploy_ingress_controller=off                    # 'on' installs a new ingress controller (may conflict with existing), 'off' uses existing ingress controller.
deploy_keycloak_apisix=on                       # Deploy Keycloak and APISIX for authentication
deploy_genai_gateway=off                        # Deploy GenAI gateway component
deploy_observability=off                        # Deploy observability stack (Prometheus, Grafana, Loki)
deploy_llm_models=on                            # Deploy LLM model inference services
deploy_ceph=off                                 # Deploy Ceph storage cluster
deploy_istio=off                                # Deploy Istio service mesh
uninstall_ceph=off                              # Uninstall existing Ceph deployment
```

**Important: Ensure at least one StorageClass exists in the cluster; if none exist, PVCs will remain unbound and the application may fail to start.**

### Step 4: Run Deployment

```bash
# Launch deployment script
./inference-stack-deploy.sh
```

**Menu Navigation:**

The deployment script provides an interactive menu system:

1. **Main Menu** - Select option 4 for Brownfield Deployment:
    ```console
    ----------------------------------------------------------
    |  Intel AI for Enterprise Inference                      |
    |---------------------------------------------------------|
    | 1) Provision Enterprise Inference Cluster               |
    | 2) Decommission Existing Cluster                        |
    | 3) Update Deployed Inference Cluster                    |
    | 4) Brownfield Deployment of Enterprise Inference        |
    |---------------------------------------------------------|
    Please choose an option (1, 2, 3 or 4):
    > 4
    ```

2. **Kubeconfig Path** - Enter the full path to your kubeconfig file:
    ```console
    Attempt 1 of 3:
    Enter the full path to the kubeconfig file to provision brownfield deployment: /path/to/your/kubeconfig
    ```

3. **Brownfield Operations Menu** - Choose your deployment operation:
    ```console
    -------------------------------------------------
    |     Brownfield Deployment Operations           |
    |------------------------------------------------|
    | 1) Deploy Inference Stack                      |
    | 2) Manage Models                               |
    |------------------------------------------------|
    Please choose an option (1 or 2):
    > 
    ```
   - **Option 1**: Deploy the complete inference stack on your existing cluster
   - **Option 2**: Add, remove, or update models after the Enterprise Inference Stack is deployed with Option 1

> **Note**: API server's TLS certificate verification is skipped to avoid TLS certificate/connection issues.

## Troubleshooting

### Managing Ingress Conflicts

For brownfield deployments, if your cluster already has an ingress controller, you can use it for the application. Set the following option in `core/inventory/inference-config.cfg`:

```properties
deploy_ingress_controller=off
```

This will skip installation of a new ingress controller and use the existing one. Ensure your ingress controller is properly configured to route traffic to the deployed services.

**Pre-deployment check:**
```bash
# Check existing ingress resources
kubectl get ingress -A
kubectl get ingressclass
kubectl get svc -A | grep ingress
```

**Verify ingress routing:**
```bash
# Check your ingress controller's service and ingress resources
kubectl get svc -A | grep ingress
kubectl get ingress -A
# Test external access using your ingress controller's NodePort or LoadBalancer IP
```

### Common Issues

| Issue | Solution |
|-------|----------|
| **kubeconfig not found** | Use absolute path: `/home/user/kubeconfig` |
| **Connection failed** | Check network/VPN, verify API server endpoint |
| **Permission denied** | Ensure kubeconfig has cluster-admin role |
| **Model deployment stuck** | Verify HuggingFace token and cluster resources |
| **Ingress conflicts** | Set `deploy_ingress_controller=off` inference config to use existing ingress controller |
| **Proxy issues** | Configure proxy settings in inference-config.cfg. See [Running behind a corporate proxy](../../running-behind-proxy.md) |
