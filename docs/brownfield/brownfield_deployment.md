# Intel® AI for Enterprise Inference - Brownfield Deployment Guide

## Overview

**Brownfield deployment** enables you to deploy the Intel AI for Enterprise Inference stack on an **existing Kubernetes cluster**. This approach leverages your current infrastructure to deploy Enterprise Inference application stack.

### Use Cases

**Perfect for:**
- Existing Kubernetes clusters (validated with vanilla Kubernetes, Amazon EKS, and Red Hat OpenShift)
- Adding AI capabilities to current infrastructure
- Preserving existing workloads and configurations
- Minimizing deployment time and infrastructure costs

**Not suitable for:**
- New cluster setup (use greenfield deployment or fresh installation instead)

### Pre-requisities

- **Node labels configured for workload placement**
  - **Infrastructure nodes** must be labeled with `role=infra`
    - Used for infrastructure components: Keycloak, APISIX, GenAI Gateway
  - **Inference nodes** must be labeled with `role=inference`
    - Used for model inference workloads
  - **Warning**: Workloads will remain in Pending state if proper node labels are not configured

- **Existing ingress controllers identified and handled**
  - If present, ingress controller must have external access configured
  - Ensure ingress controller can route traffic to deployed services
  - Verify ingress class is properly configured and functional via a valid fqdn (same fqdn and certs must be provided in `core/inventory/inference-config.cfg`)
  - Refer [Common Configuration Parameters](brownfield_deployment.md#common-configuration-parameters)

- **Sufficient cluster resources available**
  - Minimum 250GB storage capacity for model PVC
  - Adequate CPU and memory resources for model workloads
  - Check node capacity and available resources before deployment
  - Ensure at least one StorageClass to be present in the Kubernetes cluster

- **Network connectivity between all nodes verified**
  - All cluster nodes can communicate with each other
  - Nodes have access to container registries and external repositories
  - Firewall rules allow necessary traffic between nodes
  - **For remote cluster access**: Kubernetes API server port (default 6443) must be exposed in security group/firewall rules to allow deployment machine to connect to the cluster

- **DNS entries and TLS certificates prepared**
  - Valid DNS record pointing to your cluster ingress endpoint
  - TLS certificate and key files ready for HTTPS access
  - Certificate matches the DNS name configured in inference-config.cfg

- **kubeconfig file tested and working**
  - Kubeconfig has cluster-admin permissions
  - API server endpoint is accessible from deployment machine
  - Successfully tested with `kubectl cluster-info` and `kubectl get nodes`

## Deployment Steps

Refer to your platform-specific guide for detailed deployment instructions:
- [Vanilla Kubernetes Quick Start](brownfield_deployment_vanilla.md)
- [Amazon EKS Quick Start](brownfield_deployment_eks.md)
- [Red Hat OpenShift Quick Start](brownfield_deployment_openshift.md)


### Prepare Kubeconfig

The kubeconfig file must be copied from your Kubernetes control plane node to the deployment machine and the path must be provided as a user input during deployment.

**Important: Ensure the server IP/hostname in kubeconfig points to the correct Kubernetes API endpoint**

**Verify kubeconfig works from deployment machine:**

```bash
export KUBECONFIG=~/.kube/config
kubectl cluster-info
kubectl get nodes
kubectl get pods -A
```

If the kubeconfig contains a private IP and you're accessing from outside the cluster, you may need to update the server address:

```bash
# View current server address
kubectl config view --minify -o jsonpath='{.clusters[0].cluster.server}'

# Update server address if needed
kubectl config set-cluster <cluster-name> --server=https://<server-ip>:6443
```

**System-wide configuration for automation:**

For automation and playbooks that may run as root, set the `KUBECONFIG` variable in `/etc/environment`:

```bash
KUBECONFIG=/home/ubuntu/.kube/config
```

Apply the changes:

```bash
source /etc/environment
```

> **Note**: API server's TLS certificate verification is skipped to avoid TLS certificate/connection issues.


### Clone Repository

```bash
cd ~
git clone https://github.com/opea-project/Enterprise-Inference.git
cd Enterprise-Inference
```

### Common Configuration Parameters

Edit `core/inventory/inference-config.cfg`:

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
hugging_face_token=your_hugging_face_token      # HuggingFace token for model downloads
hugging_face_token_falcon3=your_hugging_face_token  # Separate token for Falcon3 models (if needed)

# Model Configuration
models=21                                       # Model selection (see supported models list - 21 is example model ID)
cpu_or_gpu=cpu                                  # Hardware accelerator: 'cpu' or 'gpu'

# Deployment Options
deploy_kubernetes_fresh=off                      # Deploy fresh Kubernetes cluster (always 'off' for brownfield)
deploy_ingress_controller=off                    # 'on' installs NGINX ingress controller, 'off' uses existing
deploy_keycloak_apisix=on                       # Deploy Keycloak and APISIX for authentication
deploy_genai_gateway=off                        # Deploy GenAI gateway component
deploy_observability=off                        # Deploy observability stack (Prometheus, Grafana, Loki)
deploy_llm_models=on                            # Deploy LLM model inference services
deploy_ceph=off                                 # Deploy Ceph storage cluster
deploy_istio=off                                # Deploy Istio service mesh
uninstall_ceph=off                              # Uninstall existing Ceph deployment
```

**Configuration Notes:**

- `deploy_ingress_controller=off`: Use this if you already have an ingress controller (NGINX, Traefik, HAProxy, etc.)
- `deploy_ingress_controller=on`: Automation will deploy NGINX ingress controller with NodePort access
- Ensure your DNS `cluster_url` resolves to your ingress controller's external endpoint
- Cluster configurations(cluster_url, cert_file and key_file) are mandatory for deployment to work.
- If using existing ingress controller, ensure it's accessible externally 

**Important: Ensure at least one StorageClass exists in the cluster; if none exist, PVCs will remain unbound and the application may fail to start.**

## Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| **kubeconfig not found** | Use absolute path: `/home/user/kubeconfig` |
| **Connection failed** | Check network/VPN, verify API server endpoint |
| **Permission denied** | Ensure kubeconfig has cluster-admin role |
| **Model deployment stuck** | Verify HuggingFace token and cluster resources |
| **Ingress conflicts** | Set `deploy_ingress_controller=off` inference config to use existing ingress controller |
| **Proxy issues** | Configure proxy settings in inference-config.cfg. See [Running behind a corporate proxy](../running-behind-proxy.md) |

## Known Limitations

- Only tested on Vanilla Kubernetes( v1.31.4), Amazon EKS(v1.33), and Red Hat OpenShift clusters(v4.19.13).
- Requires cluster-admin permissions for deployment.
- No automated rollback for failed deployments; manual intervention may be required.
- PVCs require at least one available StorageClass; unbound PVCs will cause failures.

> **Note:** Any required modifications may be made to ensure our application is compatible with the target brownfield Kubernetes cluster and the solution documentation may be updated accordingly.
