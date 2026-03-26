# Intel® AI for Enterprise Inference - Openshift (APISIX)
## Red Hat OpenShift Brownfield Deployment (Single Node OpenShift – SNO)

## Table of Contents
- [Overview](#overview)
- [Prerequisites](#prerequisites)
  - [OpenShift-Specific Requirements](#OpenShift-Specific-Requirements)
  - [Deployment Machine Requirements](#Deployment-Machine-Requirements)
  - [Pre-Deployment Validation](#Pre-Deployment-Validation)
- [Single Node Deployment Guide](#single-node-deployment-guide)
  - [1. Configure the Setup Files and Environment](#1-configure-the-setup-files-and-environment)
  - [2. Run the Deployment](#2-run-the-deployment)
  - [3. Verify the Deployment](#3-verify-the-deployment)
  - [4. Test the Inference](#4-test-the-inference)
- [Troubleshooting](#troubleshooting)
- [Summary](#summary)

---

## Overview

This guide documents a **validated brownfield deployment** of **Intel® AI for Enterprise Inference** on **Red Hat OpenShift Container Platform**, specifically **Single Node OpenShift (SNO)** running on **RHCOS**.

The deployment is designed for environments where an existing OpenShift cluster is already operational, and the inference stack must be integrated without introducing additional infrastructure components such as:

 - Kubernetes Ingress controllers
 - Istio service mesh
 - Ceph storage
 - Observability stack

The solution leverages **OpenShift Routes, router-managed TLS, local storage, and Keycloak-based authentication**, aligning with OpenShift.

---

## Prerequisites

### OpenShift-Specific Requirements

| Component | Requirement |
|---------|------------|
| OpenShift Container Platform | v4.20.0 
| Kubernetes Version | v1.33.6 |
| Node Type | Single Node OpenShift (SNO) |
| Operating System | Red Hat CoreOS (RHCOS) |
| Access | cluster-admin kubeconfig |
| OpenShift Router | Default (Routes used instead of Ingress) |
| StorageClass | local-sc |
|local storage operator | installed and bound |
| TLS | Edge termination (Router-managed) |
|Networking	| Default OpenShift Router |


### Deployment Machine Requirements
The inference stack must be deployed from a separate machine, not the SNO node.

| Component | Requirement |
|-----------|-------------|
| Deployment Model | Brownfield |
| Deployment Machine | Ubuntu 22.04 |
| Enterprise Inference Version | release-1.4.0 |
| Accelerator | CPU |
| Network | Full egress (Registry + Hugging Face) |


### Pre-Deployment Validation

**1. kubeconfig Access Verification**

Copy kubeconfig to the deployment machine:
```bash
mkdir -p ~/.kube
cp <kubeconfig> ~/.kube/config
chmod 600 ~/.kube/config
```

> **Note:** The kubeconfig provides cluster-admin access and should be protected like a root credential.


**2. DNS Resolution (If No Corporate DNS)**

If API Does Not Resolve at DNS to **etc/hosts**
```bash
sudo vi /etc/hosts
```
Add these lines and save file:
```bash
<SNO_IP> api.<cluster>.<domain>
<SNO_IP> keycloak-okd.apps.<cluster>.<domain>
<SNO_IP> okd.apps.<cluster>.<domain>
```
> If enterprise DNS is configured correctly, this step is not required.

---

## Single Node Deployment Guide

### 1. Configure the Setup Files and Environment

Clone the repository, If repo is not downloaded on target machine.

**Update the config file**

```bash
vi Enterprise-Inference/core/inventory/inference-config.cfg
```

> **Note:** Update configuration files for single node apisix deployment, Below are the changes needed.
> * Replace cluster_url with your **okd.apps.CLUSTER.DOMAIN**
> * Set `deploy_kubernetes_fresh` to "off" and `deploy_ingress_controller` to "off", as we are doing a brownfield deployment.
> * Set keycloak `keycloak_client_id` `keycloak_admin_user` `keycloak_admin_password` values
> * Add your Hugging Face token
> * Set the `cpu_or_gpu value` to "cpu" for Xeon models and "gaudi3" for Intel Gaudi 3 accelerator models
> * Set `deploy_keycloak_apisix` to "on" and Set `deploy_genai_gateway` to "off"


```
cluster_url=okd.apps.<CLUSTER>.<DOMAIN>
cert_file=~/certs/ei.crt
key_file=~/certs/ei.key
keycloak_client_id=my-client-id  
keycloak_admin_user=your-keycloak-admin-user   
keycloak_admin_password=changeme 
hugging_face_token=your_hugging_face_token
hugging_face_token_falcon3=your_hugging_face_token
models=
cpu_or_gpu=gaudi3
vault_pass_code=place-holder-123
deploy_kubernetes_fresh=off
deploy_ingress_controller=off
deploy_keycloak_apisix=on
deploy_genai_gateway=off
deploy_observability=off
deploy_llm_models=on
deploy_ceph=off
deploy_istio=off
uninstall_ceph=off
```

To support non-interactive execution of inference-stack-deploy.sh, create a file named "core/inventory/.become-passfile" with your user's sudo password

```bash
vi core/inventory/.become-passfile
chmod 600 core/inventory/.become-passfile
```

**Update hosts.yaml File**

Copy the single node preset hosts config file to the working directory:
```bash
cp -f docs/examples/single-node/hosts.yaml core/inventory/hosts.yaml
```
> Note: The ansible_user field is set to ubuntu by default. Change it to the actual username used.

### 2. Run the Deployment

> **Note:**
> The '--models' argument allows you to specify one or more models by their numeric ID. [full list of available model IDs](../../../ubuntu-22.04/iac/README.md#pre-integrated-models-list)
> If `--models` is omitted, the installer displays the full model list and prompts you to select a model interactively.

Run the setup for Gaudi 

```bash
cd core
chmod +x inference-stack-deploy.sh
./inference-stack-deploy.sh --models "1" --cpu-or-gpu "gaudi3"
```

Run the setup for CPU

```bash
cd core
chmod +x inference-stack-deploy.sh
./inference-stack-deploy.sh --models "21" --cpu-or-gpu "cpu"
```

When prompted, choose option **4) Brownfield Deployment** provide **Kubeconfig path**(e.g. ~/.kube/config **) and then select option **1) Initial deployment**

### 3. Verify the Deployment

After the inference stack deployment completes, validate that all core components, storage objects, and workloads are in a healthy state before deploying or testing models.

**1. Verify Namespaces**

Ensure required namespaces are created:
```bash
kubectl get ns | egrep "auth-apisix|default"
```
Expected:

 - default
 - auth-apisix

**2. Verify Pods Status**

```bash
kubectl get pods -A
```

Expected States:
 - All pods Running
 - No CrashLoopBackOff
 - No Pending pods

**3. Final Health Check**

Run the following checklist:
```bash
kubectl get pv
kubectl get pvc -A
kubectl get routes -A
```
Expected:

- PV = Bound
- PVC = Bound
- Route = Created

### 4. Test the Inference

**Obtain Access Token**

Before generating the access token, ensure all Keycloak-related values are correctly set in the `Enterprise-Inference/core/scripts/generate-token.sh` and these values must match with keycloak values in `Enterprise-Inference/core/inventory/inference-config.cfg`.

> **Note:** Make sure to replace BASE_URL with "**https://okd.apps.CLUSTER-NAME.DOMAIN-NAME**" where ever required

```bash
cd Enterprise-Inference/core/scripts
chmod +x generate-token.sh
. generate-token.sh
```

**Verify the Token**

After the script completes successfully, confirm that the token is available in your shell:

```bash
echo $BASE_URL
echo $TOKEN
```

If a valid token is returned (long JWT string), the environment is ready for inference testing.

**Run a test query for Gaudi:**
> Note: Replace ${BASE_URL} with your DNS

```bash
curl -k https://${BASE_URL}/Llama-3.1-8B-Instruct/v1/completions \
-X POST \
-d '{"model": "meta-llama/Llama-3.1-8B-Instruct", "prompt": "What is Deep Learning?", "max_tokens": 25, "temperature": 0}' \
-H 'Content-Type: application/json' \
-H "Authorization: Bearer $TOKEN"
```

**Run a test query for CPU:**
```bash
curl -k ${BASE_URL}/Llama-3.1-8B-Instruct-vllmcpu/v1/completions \
-X POST \
-d '{"model": "meta-llama/Llama-3.1-8B-Instruct", "prompt": "What is Deep Learning?", "max_tokens": 25, "temperature": 0}' \
-H 'Content-Type: application/json' \
-H "Authorization: Bearer $TOKEN"
```
If successful, the model will return a completion response.

---

## Troubleshooting

This document provides common deployment and runtime issues observed during Intel® AI for Enterprise Inference setup — along with step-by-step resolutions.

[**Troubleshooting Guide**](./troubleshooting.md)

---

## Summary

You’ve successfully:

- Verified system readiness
- Deployed Intel® AI for Enterprise Inference on openshift
- Tested a working model endpoint






