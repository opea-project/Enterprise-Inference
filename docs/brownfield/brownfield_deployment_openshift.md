# Intel® AI for Enterprise Inference - Red Hat OpenShift Brownfield Deployment

## Overview

This guide provides specific instructions for deploying Intel AI for Enterprise Inference on **Red Hat OpenShift Container Platform** clusters.

**[← Back to Main Brownfield Guide](brownfield_deployment.md)**

## OpenShift-Specific Requirements

### Required Components

| Component | Requirement | Notes |
|-----------|-------------|-------|
| **OpenShift Cluster** | v4.19.13 | Validated on OpenShift v4.19.13 (Kubernetes v1.32.8) |
| **Deployment Machine** | Ubuntu 22.04 or RHEL 8+ | Machine running the automation |
| **Network Access** | Unrestricted cluster API | Required for deployment automation |
| **kubeconfig** | Admin permissions | Full cluster access needed (cluster-admin role) |
| **Storage** | StorageClass available | Required for PVC (Minimum 250GB for models) |
| **DNS & Certificates** | TLS setup | For external route access via OpenShift router |
| **OpenShift Router** | Default router | Built-in ingress/route mechanism |
| **Proxy Settings** | Corporate proxy config | See [Running behind a corporate proxy](../running-behind-proxy.md) if required |

### OpenShift Prerequisites

#### 1. OpenShift Router Configuration

OpenShift uses Routes instead of standard Kubernetes Ingress. The default router must be functional:

#### 2. Security Context Constraints (SCC)

OpenShift has stricter security policies than vanilla Kubernetes. The deployment automation handles SCC configuration, but you should be aware of:

- **Default SCC**: Most workloads run with `restricted-v2` SCC
- **Privileged operations**: Some components may require elevated permissions
- **Service accounts**: Properly configured for required SCCs

### Authentication Requirements

- **OpenShift Credentials**: Login to OpenShift cluster via `oc login` (cluster-admin role required)
- See [main guide](brownfield_deployment.md) for HuggingFace token requirements

### OpenShift-Specific Pre-requisites

For general prerequisites (node labels, network connectivity, kubeconfig, resources, etc.), see the [main guide prerequisites section](brownfield_deployment.md#pre-requisities).

**OpenShift-Specific:**

- **Security Context Constraints (SCC) awareness**
  - Understand OpenShift's SCC model
  - Automation will configure necessary SCCs
  - Some workloads may require `anyuid` or `privileged` SCC

- **OpenShift router and DNS**
  - Valid DNS record pointing to OpenShift router (*.apps.cluster.domain)
  - OpenShift router can use default wildcard certificates

## Quick Start Deployment

### Step 1: Prepare Kubeconfig

See [main guide - Prepare Kubeconfig](brownfield_deployment.md#prepare-kubeconfig) for preparing the kubeconfig file to connect to the cluster.

### Step 2: Clone Repository

See [main guide - Clone Repository](brownfield_deployment.md#step-2-clone-repository) for repository cloning instructions.

### Step 3: Configure OpenShift Deployment

See [main guide - Common Configuration Parameters](brownfield_deployment.md#common-configuration-parameters) for detailed configuration instructions.

**OpenShift-Specific Configuration Notes:**

- `cluster_url`: Use the OpenShift apps wildcard domain (e.g., `apps.cluster.example.com`)
- `deploy_ingress_controller=off`: **Required** - Must use existing OpenShift router
- Routes will be created automatically instead of Ingress resources
- OpenShift router handles TLS termination

### Step 4: Run Deployment

```bash
# Launch deployment script
./inference-stack-deploy.sh
```

**Menu Navigation:**

Select **option 4** for Brownfield Deployment, provide your kubeconfig path, and choose:
- **Option 1**: Deploy the complete inference stack on your existing cluster
- **Option 2**: Add, remove, or update models after initial deployment (To be run after Option 1)


After deployment, OpenShift Routes will be created automatically:

```bash
# Get all routes
oc get routes -A

# Example output:
# NAMESPACE               NAME              HOST/PORT                                    PATH       SERVICES          PORT    TERMINATION
# genai-gateway           litellm-gateway   api.apps.cluster.example.com                            litellm-gateway   http    edge
# default                 keycloak          keycloak-api.apps.cluster.example.com                   keycloak          http    edge
# genai-gateway           langfuse          trace-api.apps.cluster.example.com                      langfuse          http    edge
# observability           grafana           observability-api.apps.cluster.example.com              grafana           http    edge  
```

Access the services via the route URLs:
- `https://api.apps.cluster.example.com` - LiteLLM Gateway
- `https://keycloak-api.apps.cluster.example.com` - Keycloak (if deployed)
- `https://trace-api.apps.cluster.example.com` - Langfuse/Trace (if GenAI gateway deployed)
- `https://observability-api.apps.cluster.example.com` - Grafana (if Observability deployed)


## Troubleshooting

### OpenShift-Specific Issues

For common issues (kubeconfig not found, connection failed, permission denied, etc.), see the [main guide troubleshooting section](brownfield_deployment.md#troubleshooting).

**OpenShift-Specific Problems:**

| Issue | Solution |
|-------|----------|
| **Route not accessible** | Verify OpenShift router is running: `oc get clusteroperator ingress` |
| **Permission denied (SCC)** | Check security context constraints and service account permissions |
| **Image pull errors** | Verify image registry access and pull secrets |
| **Pod security violations** | Review SCC policies and adjust if necessary (automation handles most cases) |
| **Storage class not found** | Verify at least one StorageClass exists: `oc get storageclass` |
| **Keycloak realm creation failed** | Verify route is accessible and DNS resolves correctly |
| **Pod stuck in Pending** | Check node labels (`role=infra`, `role=inference`) and resources |


## OpenShift-Specific Limitations

- **OpenShift Service Mesh** (Istio) is separate from the deploy_istio option and requires separate configuration
- **Privileged operations** may require additional SCC permissions beyond what automation configures

For general limitations, see the [main brownfield deployment guide](brownfield_deployment.md#known-limitations).
