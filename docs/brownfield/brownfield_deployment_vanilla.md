# Intel® AI for Enterprise Inference - Vanilla Kubernetes Brownfield Deployment

## Overview

This guide provides specific instructions for deploying Intel AI for Enterprise Inference on **vanilla Kubernetes clusters** (e.g., deployed using kubespray, kubeadm, or similar tools).

**[← Back to Main Brownfield Guide](brownfield_deployment.md)**

## Vanilla Kubernetes Requirements

### Required Components

| Component | Requirement | Notes |
|-----------|-------------|-------|
| **Kubernetes Cluster** | v1.31.4 | Validated on Server version v1.31.4 with kubespray v2.27.0 |
| **Deployment Machine** | Ubuntu 22.04 | Machine running the automation |
| **Network Access** | Unrestricted cluster API | Required for deployment automation |
| **kubeconfig** | Admin permissions | Full cluster access needed (cluster-admin role) |
| **Storage** | StorageClass available | Required for PVC (Minimum 250GB for models) |
| **DNS & Certificates** | TLS setup | For external LiteLLM gateway access |
| **Ingress Controller** | Optional | Can use existing or deploy new (NGINX, Traefik, etc.) |
| **Proxy Settings** | Corporate proxy config | See [Running behind a corporate proxy](../running-behind-proxy.md) if required |

### Vanilla Kubernetes Prerequisites

For general prerequisites (node labels, network connectivity, kubeconfig, resources, DNS, etc.), see the [main guide prerequisites section](brownfield_deployment.md#pre-requisities).

Verify ingress class is properly configured and functional via a valid fqdn (same fqdn and certs must be provided in `core/inventory/inference-config.cfg`)

## Quick Start Deployment

### Step 1: Prepare Kubeconfig

See [main guide - Prepare Kubeconfig](brownfield_deployment.md#prepare-kubeconfig) for preparing the kubeconfig file to connect to the cluster.

### Step 2: Clone Repository

See [main guide - Clone Repository](brownfield_deployment.md#clone-repository) for repository cloning instructions.

### Step 3: Configure Deployment

See [main guide - Common Configuration Parameters](brownfield_deployment.md#common-configuration-parameters) for detailed configuration instructions.

### Step 4: Run Deployment

```bash
cd ~/Enterprise-Inference/core
./inference-stack-deploy.sh
```

**Menu Navigation:**

Select **Option 4** for Brownfield Deployment, provide your kubeconfig path, and choose:
- **Option 1**: Deploy the complete inference stack on your existing cluster
- **Option 2**: Add, remove, or update models after initial deployment (To be run after Option 1)


### Step 5: Verify Deployment

After deployment completes, verify the installation:

```bash
# Check all pods are running
kubectl get pods -A

# Check services
kubectl get svc -A

# Check ingress resources
kubectl get ingress -A

# Check persistent volume claims
kubectl get pvc -A

```

For accessing deployed models refer [accessing-deployed-models](../accessing-deployed-models.md)

## Troubleshooting

### Common Issues

For general troubleshooting guidance, see the [main guide troubleshooting section](brownfield_deployment.md#troubleshooting).

**Vanilla Kubernetes-Specific Problems:**

| Issue | Solution |
|-------|----------|
| **PVC unbound** | Verify StorageClass exists: `kubectl get sc` |
| **Ingress not accessible** | Check ingress controller is running and externally accessible |
| **ImagePullBackOff** | Check container registry access and image names |

For general limitations, see the [main brownfield deployment guide](brownfield_deployment.md#known-limitations).
