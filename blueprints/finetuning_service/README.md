# Fine-Tuning Service

Copyright (C) 2024-2025 Intel Corporation
SPDX-License-Identifier: Apache-2.0

Reference fine-tuning solution for Intel® AI for Enterprise Inference that deploys a complete LLM fine-tuning stack alongside the existing inference cluster.

## What Gets Deployed

| Component | Namespace | Purpose |
|-----------|-----------|--------|
| Fine-Tuning API | `finetuning-api` | OpenAI-compatible API for managing fine-tuning jobs |
| Data Preparation Service | `dataprep` | Document processing, Q&A dataset generation |
| Celery Workers | `dataprep` | Async processing (Docling, LlamaIndex) |
| Fine-Tuning UI | `finetuning-ui` | Web interface |
| PostgreSQL (x2) | `dataprep`, `finetuning-api` | Persistent storage per service |
| Redis (x2) | `dataprep`, `finetuning-api` | Caching and task queuing |
| MinIO | `dataprep` | Shared object storage for training files |

> **Note — Nvidia GPU Training Engine (Unsloth):** The actual GPU fine-tuning workload runs on a **separate Nvidia GPU machine**, not on the Enterprise Inference cluster. To deploy the Nvidia/Unsloth fine-tuning engine on that machine, follow the instructions in [src/finetuning-engine/README.md](src/finetuning-engine/README.md). Once it is running, set its URL as `finetune_training_backend_url` in `core/inventory/finetune-config.cfg` before deploying this service.

## Directory Structure

```
blueprints/finetuning_service/
├── README.md                          # This file
├── finetune-config.cfg                # User-facing configuration
├── playbooks/
│   ├── deploy-all.yml                 # Main orchestration playbook
│   ├── deploy-finetuning-api.yml      # Fine-Tuning API
│   ├── deploy-dataprep.yml            # Data Preparation Service
│   ├── deploy-ui.yml                  # Fine-Tuning UI
│   └── build-images.yml               # Container image builds
├── vars/
│   └── finetune-plugin-vars.yml       # Internal deployment variables
├── scripts/
│   └── setup-keycloak-finetuning.sh   # Keycloak realm/client setup
└── src/
    ├── api/                           # Fine-Tuning API source (FastAPI)
    ├── dataprep/                      # Data Preparation source (FastAPI)
    ├── ui/                            # Fine-Tuning UI source (Next.js)
    └── finetuning-engine/             # Nvidia/Unsloth GPU training backend
```

## Quick Start

### Step 1: Deploy the Nvidia Fine-Tuning Engine (GPU machine)

Before deploying the cluster-side services, the Nvidia/Unsloth training backend must be running on a GPU machine. Follow the instructions in [src/finetuning-engine/README.md](src/finetuning-engine/README.md).

### Step 2: Configure

Edit `core/inventory/inference-config.cfg`:

```properties
deploy_finetune_plugin=on
finetune_training_backend_url=https://your-nvidia-gpu-server:8443
```

### Step 3: Generate Secrets

```bash
cd core/scripts
./generate-vault-secrets.sh
```

### Step 4: Deploy

```bash
cd core
./inference-stack-deploy.sh
```

Choose option **1** (Fresh Install) or **3** (Update Cluster).

### Step 5: Access

After successful deployment:

- **UI**: `https://<cluster-url>/enterprise-ai/ui`
- **API docs**: `https://<cluster-url>/enterprise-ai/training/api/docs`
- **Data Prep docs**: `https://<cluster-url>/enterprise-ai/dataprep/docs`

## Configuration

### Required Settings (`core/inventory/inference-config.cfg`)

```properties
deploy_finetune_plugin=on
finetune_training_backend_url=https://your-nvidia-gpu-server:8443
```

### Advanced Settings (`blueprints/finetuning_service/vars/finetune-plugin-vars.yml`)

Edit this file to customise:
- Resource requests/limits (CPU, Memory)
- Replica counts
- Storage sizes
- Image repositories and tags
- Base URL paths

## Manual Deployment (without inference-stack-deploy.sh)

Run from the `core/` directory:

```bash
ansible-playbook -i inventory/hosts.yml \
  ../blueprints/finetuning_service/playbooks/deploy-all.yml \
  --vault-password-file inventory/.vault-passfile
```

Or deploy individual components:

```bash
# Data Preparation Service
ansible-playbook -i inventory/hosts.yml \
  ../blueprints/finetuning_service/playbooks/deploy-dataprep.yml \
  --vault-password-file inventory/.vault-passfile

# Fine-Tuning API
ansible-playbook -i inventory/hosts.yml \
  ../blueprints/finetuning_service/playbooks/deploy-finetuning-api.yml \
  --vault-password-file inventory/.vault-passfile

# Fine-Tuning UI
ansible-playbook -i inventory/hosts.yml \
  ../blueprints/finetuning_service/playbooks/deploy-ui.yml \
  --vault-password-file inventory/.vault-passfile
```

## Deployment Status Checks

```bash
kubectl get pods -n dataprep
kubectl get pods -n finetuning-api
kubectl get pods -n finetuning-ui
```

## Troubleshooting

### Pod not starting

```bash
kubectl logs -n <namespace> <pod-name>
```

### Keycloak authentication issues

Re-run the Keycloak setup script:

```bash
bash blueprints/finetuning_service/scripts/setup-keycloak-finetuning.sh
```

Verify both clients exist in the Keycloak admin console: `finetuning-backend` (confidential) and `finetuning-ui` (public).

### Database connection issues

```bash
kubectl get pods -n dataprep | grep postgres
kubectl get pods -n finetuning-api | grep postgres
```

## Updating Configuration

```bash
# Edit config
vi core/inventory/inference-config.cfg

# Redeploy (choose option 3 - Update)
cd core && ./inference-stack-deploy.sh
```

## Uninstalling

```bash
kubectl delete namespace dataprep
kubectl delete namespace finetuning-api
kubectl delete namespace finetuning-ui
```

Or disable in config and redeploy:

```properties
deploy_finetune_plugin=off
```
