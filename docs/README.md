# Quick Start
To set up prerequisities and quickly deploy Intel® AI for Enterprise Inference on a single node, follow the steps in the [**Single Node Deployment Guide**](./single-node-deployment.md). Otherwise, proceed to the section below for all deployment options.

# Complete Intel® AI for Enterprise Inference Cluster Setup

## Prerequisites
Complete all [prerequisites](./prerequisites.md).
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
- To deploy custom models from HuggingFace, follow the [HuggingFace Deployment Guide](./deploy-llm-model-from-hugging-face.md)

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
