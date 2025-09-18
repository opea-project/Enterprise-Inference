# TLDR;
# Getting Started
To setup prerequisites and quickstart deployment of Intel® AI for Enterprise Inference on a single node follow steps here [**Quick Start Guide**](./single-node-deployment.md)

> 🚀 **New**: Automated Gaudi firmware and driver management! See [Gaudi Prerequisites](./gaudi-prerequisites.md) for automated setup scripts.


# Intel® AI for Enterprise Inference Cluster Setup

## Prerequisites
- Review [System Requirements](./prerequisites.md)
---
## Deployment Options

| Deployment Type                         | Description                                                  |
|-----------------------------------------|--------------------------------------------------------------|
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

- `inventory/hosts.yaml` – Cluster inventory and topology ([Single-Node Sample](./examples/single-node/hosts.yaml), [Multi-Node Guide](./examples/multi-node/hosts.yaml))
- `inference-config.cfg` – Component-level deployment config ([Sample](./configuring-inference-config-cfg-file.md))
---
## Deployment Command
Run the following script to deploy the inference platform:
```bash
bash inference-stack-deploy.sh
```
---
## Post-Deployment

- [Access Deployed Models](./accessing-deployed-models.md)
- [Observability & Monitoring](./observability.md)
