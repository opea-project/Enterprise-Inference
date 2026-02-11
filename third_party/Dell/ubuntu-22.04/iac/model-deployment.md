# Intel® AI for Enterprise Inference — Model Deployment User Guide

## Table of Contents

1. [Overview](#1-overview)
2. [Environment Prerequisites](#2-environment-prerequisites)
3. [Model Deployment Workflow](#3-model-deployment-workflow)
   - [Deploy Models from Enterprise Inference Catalog](#31-deploy-models-from-enterprise-inference-catalog)
   - [Deploy Models Directly from Hugging Face](#32-deploy-models-directly-from-hugging-face)
4. [Undeploy Models](#4-undeploy-models)
   - [Undeploy Models from Enterprise Inference Catalog](#41-undeploy-models-from-enterprise-inference-catalog)
   - [Undeploy Models Deployed from Hugging Face](#42-undeploy-models-deployed-from-hugging-face)

## 1. Overview

This guide outlines the standard procedure for deploying models on an Enterprise Inference cluster using the `inference-stack-deploy.sh` script.

---

## 2. Environment Prerequisites

- **Host System:** Control plane or master node with access to the inference stack
- **Cluster Access:** Existing or newly provisioned Kubernetes cluster
- **Certificates:** Valid cluster certificate (`cert.pem`) and private key (`key.pem`)
- **Hugging Face Token:** Required for downloading models from Hugging Face
- **Script Path:** `~/Enterprise-Inference/core/inference-stack-deploy.sh`

---

## 3. Model Deployment Workflow

1. Deploy from pre-integrated Enterprise Inference model catalog
2. Deploy directly from Hugging Face

Both use the same interactive script and menu flow.

### 3.1 Deploy Models from Enterprise Inference Catalog

This method deploys pre-integrated and validated models optimized for Enterprise Inference.

**Step 1: Run the Deployment Script**

```bash
bash ~/Enterprise-Inference/core/inference-stack-deploy.sh
```

**Step 2: Navigate Through the Menus**

Choose the following options from the menu:

**3** – Update Deployed Inference Cluster

**2** – Manage LLM Models

**1** – Deploy Model

**Step 3: Select Model to Deploy**

The script displays a list of available models and their corresponding numeric IDs based on the selected deployment type (CPU or Gaudi).

When prompted to `Enter numbers of models to deploy/remove (comma-separated)`, enter the model ID you want to deploy (example: `1`).

**Step 4: Confirm Deployment**

When prompted to `Do you wish to continue? (y/n)`, type **y** to proceed.

**Once confirmed:**
- The model is deployed automatically to the inference cluster.
- All required Kubernetes Pods, Services, and Endpoints are created.

**Test:**

Run the following command to verify that the model pod is in the `Running` state.
```bash
kubectl get pods
```
---

### 3.2 Deploy Models Directly from Hugging Face

This option allows deploying any Hugging Face model, including models not pre-validated by Enterprise Inference.

**Step 1: To deploy**
```bash
bash ~/Enterprise-Inference/core/inference-stack-deploy.sh
```
**Step 2: Navigate Through the Menus**

Choose the following options from the menu:

**3** – Update Deployed Inference Cluster

**2** – Manage LLM Models

**4** – Deploy Model from Hugging Face

**Step 3: Provide Hugging Face Model Details**

When prompted to `Enter the Hugging Face Model ID`, enter the desired Hugging Face model ID (example: `mistralai/Mistral-7B-v0.3`).

> Note: The model(mistralai/Mistral-7B-v0.3) above is only an example. You can enter any compatible Hugging Face model (CPU or Gaudi), depending on your deployment type.

**Step 4: Provide Deployment name for the model**

When prompted to `Enter the Hugging Face Model ID`, enter the desired Hugging Face model ID (example: `mistralai/Mistral-7B-v0.3`).

> **Naming rules:**
> - Lowercase letters only
> - Numbers and hyphens allowed
> - No spaces or special characters
> - Must follow Kubernetes naming conventions

**Step 5: Provide Tensor Parallel Size (Gaudi Only)**

Set the tensor parallel size based on available Gaudi cards.

> Note: > **Note:** This option deploys a model that has not been pre-validated. Ensure the tensor parallel size is configured correctly. An incorrect value may cause the model to remain in a "Not Ready" state.

**Step 6: Confirm Deployment**

When prompted to `Do you wish to continue? (y/n)`, type **y** to proceed.

**Test**

Run the following command to verify that the model pod is in the `Running` state:

```bash
kubectl get pods
```
---

## 4. Undeploy Models

Enterprise Inference allows you to safely undeploy models that were deployed either from:
- The Enterprise Inference model catalog
- Directly from Hugging Face

### 4.1 Undeploy Models from Enterprise Inference Catalog

This method is used for models deployed through pre-integrated and validated models for Enterprise Inference.

**Step 1: Run the Deployment Script**
```bash
bash ~/Enterprise-Inference/core/inference-stack-deploy.sh
```
**Step 2: Navigate Through the Menus**

Choose the following options from the menu:

**3** – Update Deployed Inference Cluster

**2** – Manage LLM Models

**2** – Undeploy Model

**Step 3: Select Model to Remove**

The script displays a list of available models with their model IDs based on the deployment type (CPU or Gaudi).

When Prompted to `Enter numbers of models to deploy/remove (comma-separated)` - Enter the model ID you want to remove(Example: 1)

**Step 4: Confirm Model Removal**

When prompted to `Do you wish to continue? (y/n)`, type **y** to proceed.
> CAUTION: Removing the Inference LLM Model will also remove its associated services and resources, which may cause service downtime and potential data loss.

**Once confirmed:**
 - The model deployment is deleted
 - All associated Kubernetes resources are removed

**Test**

Run below command to confirm, if the model pod is deleted.
```bash
kubectl get pods
```
---

### 4.2 Undeploy Models Deployed from Hugging Face

To remove Models deployed via Deploy Model from Hugging Face

**Step 1: Run the Script**
```bash
bash ~/Enterprise-Inference/core/inference-stack-deploy.sh
```
**Step 2: Navigate Through the Menus**

Choose the following options from the menu:

**3** – Update Deployed Inference Cluster

**2** – Manage LLM Models

**5** – Remove Model using deployment name

**Step 3: Provide Deployment Name**

When prompted to `Enter Deployment Name for the Model`, provide a deployment name (example: `mistral-7b-v0-3`).

> The deployment name must exactly match the name used during model deployment.

**Step 4: Confirm Removal**

When prompted to `Do you wish to continue? (y/n)`, type **y** to proceed.
> CAUTION: Removing the Inference LLM Model will also remove its associated services and resources, which may cause service downtime and potential data loss.

**Once confirmed:**
 - The model deployment is deleted
 - All associated Kubernetes resources are removed

**Test**

Run below command to confirm, if the model pod is deleted.
```bash
kubectl get pods
```
 