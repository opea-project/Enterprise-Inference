# Getting Started with Intel® AI for Enterprise Inference on IBM Cloud

This guide provides an overview of deployment options for Intel® AI for Enterprise Inference (Enterprise Inference) on IBM Cloud and helps you select the appropriate deployment pattern for your requirements.

## What is Intel® AI for Enterprise Inference?

Intel AI for Enterprise Inference is an IBM Cloud deployable architecture that automates the deployment of OpenAI-compatible AI inference endpoints powered by Intel® Gaudi® 3 AI accelerators and Intel® Xeon® processors. It packages everything you need - Kubernetes, model serving, authentication, and monitoring - into a single, automated deployment.

## Before You Begin: Choosing the Right Configuration

Before deploying Intel AI for Enterprise Inference, it's important to understand the capabilities of Intel® Gaudi® 3 AI accelerators and select the appropriate configuration for your AI workload requirements. Please review our [Sizing Guide](./sizing-guide.md) which provides:

- Introduction to Intel® Gaudi® 3 AI Accelerator capabilities
- AI Model Hosting Requirements to help you choose the optimal configuration
- Performance metrics for different model sizes and use cases

## Deployment Architecture

Intel AI for Enterprise Inference supports both single-node and multi-node deployment architectures:

- **Single-node deployment**: All components run on a single Intel® Gaudi® 3 AI accelerator server - ideal for development, testing, and smaller workloads
- **Multi-node deployment**: Distributed architecture with separate control plane and worker nodes - ideal for production, high availability, and scaling

## Deployment Patterns

Intel AI for Enterprise Inference provides two deployment patterns to accommodate different infrastructure requirements and organizational preferences.

### Quickstart Pattern

The Quickstart pattern is designed for organizations with existing IBM Cloud infrastructure who require rapid deployment.

**Use case:** Existing IBM Cloud environments with established networking infrastructure.

**Requirements:**
- Existing VPC, subnet, and security groups
- Deployment time: ~40 minutes

**Documentation:** [Quickstart Deployment Guide](./quickstart-deployment.md)

### Standard Pattern

The Standard pattern provides complete infrastructure automation and is suitable for new environments or scenarios requiring full infrastructure control.

**Use case:** New deployments or environments requiring complete infrastructure provisioning.

**Features:**
- Automated creation of all networking components
- Automated security group configuration
- Deployment time: ~45 minutes

**Documentation:** [Standard Deployment Guide](./standard-deployment.md)

## Pattern Selection Guide

Use the following criteria to determine the appropriate deployment pattern:

```
Infrastructure Assessment:
├─ Existing VPC infrastructure available → Quickstart Pattern
│   ├─ UI-based deployment → [Quickstart UI Guide](./quickstart-deployment.md#ui-deployment)
│   └─ CLI-based deployment → [Quickstart CLI Guide](./quickstart-deployment.md#cli-deployment)
└─ New infrastructure required → Standard Pattern
    ├─ UI-based deployment → [Standard UI Guide](./standard-deployment.md#ui-deployment)
    └─ CLI-based deployment → [Standard CLI Guide](./standard-deployment.md#cli-deployment)
```

## Supported Models

The following large language models are supported for deployment:

| Model Name 								| Cards Required       		| Storage | Model ID |
|-------------------------------------------|---------------------------|---------|----------|
| meta-llama/Llama-3.1-8B-Instruct  		| 1 	  					| 20GB    | 1  		 |
| meta-llama/Llama-3.1-405B-Instruct 		| 8       					| 900GB   | 3		 |
| meta-llama/Llama-3.3-70B-Instruct			| 4       					| 150GB   | 4 		 |
| meta-llama/Llama-4-Scout-17B-16E-Instruct | 4       					| 200GB   | 5 		 |
| Qwen/Qwen2.5-32B-Instruct					| 1       					| 70GB    | 6 		 |

> **Note:** Additional models can be deployed or existing models can be removed after initial deployment by accessing the deployment instance.
>
> ### Quota Increase for Gaudi 3 - IBM Cloud Quick Start Guide [Quota Increase for Gaudi 3](./quota-increase.md)
>

### Required Components

All deployments require the following components:

1. **IBM Cloud API Key** - [Create an API key](https://cloud.ibm.com/iam/apikeys)
2. **IBM Cloud SSH Key** - For secure instance access
3. **Hugging Face Token** - For model downloads and licensing

### Production Deployment Requirements

Production deployments additionally require:

4. **Domain Name** - For HTTPS access (example: ai.yourcompany.com)
5. **TLS Certificate** - For secure connections

### Development Environment Configuration

Development and testing environments may use default configuration values for domain and TLS settings. The deployment will use `api.example.com` as the default cluster URL, suitable for internal cluster access.

## Next Steps

1. Follow the appropriate deployment guide:
   - [Quickstart Deployment](./quickstart-deployment.md)
   - [Standard Deployment](./standard-deployment.md)
2. Consult the [Accessing Deployed Models Guide](https://github.com/opea-project/Enterprise-Inference/blob/main/docs/accessing-deployed-models.md) for API usage instructions
3. Review the [Intel AI for Enterprise Inference Documentation](https://github.com/opea-project/Enterprise-Inference/tree/main/docs) for complete project documentation