# Quick Start
To set up prerequisities and quickly deploy Intel® AI for Enterprise Inference on a single node, follow the steps in the [**Single Node Deployment Guide**](./single-node-deployment.md). Otherwise, proceed to the section below for all deployment options.

> 🚀 **New**: Automated Gaudi firmware and driver management! See [Gaudi Prerequisites](./gaudi-prerequisites.md) for automated setup scripts.

# Complete Intel® AI for Enterprise Inference Cluster Setup

## Prerequisites
Complete all [prerequisites](./prerequisites.md).
---
## Deployment Options

| Deployment Type                         | Description                                                  |
|-----------------------------------------|--------------------------------------------------------------|
| **Single Node (vLLM, non‑production)**  | For Quick Testing on Intel® Xeon® processors using vLLM Docker ([Guide](../core/scripts/vllm-quickstart/README.md))               |
| **Single Node**                         | Quick start for testing or lightweight workloads ([Guide](./single-node-deployment.md)) |
| **Single Master, Multiple Workers**     | For higher throughput workloads ([Guide](./inventory-design-guide.md#single-master-multiple-workload-node-deployment)) |
| **Multi-Master, Multiple Workers**      | Recommended for HA enterprise clusters ([Guide](./inventory-design-guide.md#multi-master-multi-workload-node-deployment)) |
---
## Supported Models
- View the [Pre-validated Model List](./supported-models.md)
- To deploy custom models from Hugging Face, follow the [Hugging Face Deployment Guide](./deploy-llm-model-from-hugging-face.md)

> 💡 Both validated and custom models are supported to meet diverse enterprise needs.
---
## Configuration Files
Two files are required before deployment:

- `inventory/hosts.yaml` – Cluster inventory and topology for [single node](./examples/single-node/hosts.yaml) and [multi-node](./examples/multi-node/hosts.yaml))
- `inference-config.cfg` – Component-level deployment config [example](./configuring-inference-config-cfg-file.md)
---
## Deployment Command
Run the following script to deploy the inference platform:
```bash
bash inference-stack-deploy.sh
```
---
## Post-Deployment

- [Getting Started Example](./getting-started-example.md)
- [Access Deployed Models](./accessing-deployed-models.md)
- [Observability & Monitoring](./observability.md)

## Intel® AI for Enterprise Inference - Brownfield Deployment

Intel® AI for Enterprise Inference supports brownfield deployment, allowing you to deploy the inference stack on an existing Kubernetes cluster without disrupting current workloads. This approach leverages your current infrastructure and preserves existing workloads and configurations.

For brownfield deployment guide, refer [Brownfield Deployment Guide](brownfield/brownfield_deployment.md).




