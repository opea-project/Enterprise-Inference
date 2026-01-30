# KServe Deployment Guide for Enterprise Inference

## Overview

This guide provides instructions for deploying LLM inference services using **KServe** with **vLLM backend** on Intel platforms (Xeon CPUs and Gaudi AI Accelerators). KServe is a Kubernetes-native model serving platform that provides serverless inference, autoscaling, and advanced deployment strategies.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Architecture](#architecture)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Deployment Methods](#deployment-methods)
- [Platform-Specific Deployment](#platform-specific-deployment)
- [Accessing Models](#accessing-models)
- [Monitoring and Observability](#monitoring-and-observability)
- [Troubleshooting](#troubleshooting)
- [Advanced Configuration](#advanced-configuration)

## Prerequisites

### System Requirements

- Kubernetes cluster (v1.24+) or OpenShift (v4.12+)
- kubectl configured to access the cluster
- Helm 3.x installed
- Ansible 2.14+ installed on the deployment machine

### Hardware Requirements

**For Intel Xeon deployments:**
- Intel Xeon Scalable Processors (3rd Gen or later recommended)
- Minimum 64GB RAM (128GB+ recommended for larger models)
- 100GB+ available storage for model weights

**For Intel Gaudi deployments:**
- Intel Gaudi or Gaudi3 AI Accelerators
- Minimum 128GB RAM
- Habana drivers and firmware installed

### Software Prerequisites

- KServe operator (will be installed automatically)
- Knative Serving (optional, for advanced scaling features)
- Istio or other service mesh (optional)
- Cert-manager (recommended for webhook certificates)

## Architecture

KServe provides a serverless inference platform with the following components:

```
┌─────────────────────────────────────────────────────────────┐
│                     Ingress / Service Mesh                   │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                  KServe InferenceService                     │
│  ┌──────────────────────────────────────────────────────┐  │
│  │             Predictor Container                       │  │
│  │  ┌─────────────────────────────────────────────┐    │  │
│  │  │  vLLM Runtime (OpenAI-compatible API)        │    │  │
│  │  │  - Model: Llama, Qwen, DeepSeek, etc.       │    │  │
│  │  │  - Backend: vLLM on Xeon or Gaudi           │    │  │
│  │  └─────────────────────────────────────────────┘    │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│              Storage (PVC / S3 / Model Repository)          │
└─────────────────────────────────────────────────────────────┘
```

### Key Features

- **Serverless Inference**: Automatic scaling to zero when idle
- **Autoscaling**: Scale based on request load and custom metrics
- **Multi-Framework Support**: Deploy vLLM, TGI, or custom runtimes
- **Canary Rollouts**: Gradual model version updates
- **Model Monitoring**: Built-in metrics and observability

## Quick Start

### 1. Install KServe Operator

Edit `core/inventory/inference-config.cfg`:

```bash
deploy_kserve_operator=on
```

Run the Ansible playbook:

```bash
cd core
ansible-playbook -i inventory/hosts.yaml playbooks/deploy-kserve-operator.yml
```

This will:
- Install KServe CRDs and controller
- Configure Intel-optimized ClusterServingRuntimes
- Set up necessary RBAC permissions

### 2. Deploy a Model with KServe

Edit `core/inventory/metadata/vars/inference_kserve.yml`:

```yaml
# Enable KServe model deployment
kserve_cpu_deployment: true  # For Xeon
# OR
kserve_gpu_deployment: true  # For Gaudi

# Select platform
kserve_platform: "xeon"  # Options: xeon, gaudi, gaudi3

# Specify models to deploy
kserve_model_name_list:
  - "meta-llama/Llama-3.2-3B-Instruct"
  - "Qwen/Qwen2.5-7B-Instruct"
```

Deploy models:

```bash
ansible-playbook -i inventory/hosts.yaml playbooks/deploy-kserve-models.yml
```

### 3. Verify Deployment

Check InferenceService status:

```bash
kubectl get inferenceservices -n default
```

Expected output:

```
NAME                              URL                                              READY   PREV   LATEST
kserve-meta-llama-llama-3-2-3b   http://kserve-meta-llama-llama-3-2-3b.default   True           100
```

## Configuration

### KServe Configuration Variables

Edit `core/inventory/metadata/vars/inference_kserve.yml`:

```yaml
# KServe version
kserve_version: "0.13.0"

# Installation flags
install_kserve: true
install_kserve_runtimes: true
configure_intel_runtimes: true

# Model deployment settings
kserve_model_name_list:
  - "meta-llama/Llama-3.2-3B-Instruct"

# Deployment method
kserve_deployment_method: "helm"  # Options: helm, kubectl

# Backend selection
kserve_backend: "vllm"  # Options: vllm, tgi, custom

# Storage configuration
kserve_pvc_enabled: true
kserve_pvc_size: "100Gi"
kserve_pvc_storage_class: ""  # Leave empty for default

# Autoscaling configuration
kserve_autoscaling_enabled: true
kserve_autoscaling_min_replicas: 1
kserve_autoscaling_max_replicas: 4

# Monitoring
kserve_service_monitor_enabled: true  # Requires prometheus-operator

# Network configuration
kserve_ingress_enabled: false
kserve_apisix_route_enabled: true  # For API gateway integration
```

### Platform-Specific Configuration

#### Xeon Configuration

File: `core/helm-charts/kserve/xeon-values.yaml`

```yaml
image:
  repository: public.ecr.aws/q9t5s3a7/vllm-cpu-release-repo
  tag: "v0.10.2"

resources:
  limits:
    cpu: "32"
    memory: 128Gi
  requests:
    cpu: "16"
    memory: 64Gi

nodeSelector:
  intel.feature.node.kubernetes.io/cpu-cpuid.AVX512VNNI: "true"
```

#### Gaudi Configuration

File: `core/helm-charts/kserve/gaudi-values.yaml`

```yaml
image:
  repository: vault.habana.ai/gaudi-docker/1.18.0/ubuntu22.04/habanalabs/pytorch-installer-2.5.1
  tag: "latest"

accelDevice: "habana.ai/gaudi"
accelDeviceCount: 1

resources:
  limits:
    habana.ai/gaudi: 1
    cpu: "32"
    memory: 256Gi
  requests:
    habana.ai/gaudi: 1
    cpu: "16"
    memory: 128Gi

nodeSelector:
  node.kubernetes.io/instance-type: gaudi
```

## Deployment Methods

### Method 1: Ansible Playbook (Recommended)

**Advantages:**
- Automated end-to-end deployment
- Handles dependencies and configuration
- Consistent across environments

**Steps:**

1. Configure variables in `inventory/metadata/vars/inference_kserve.yml`
2. Run playbook:

```bash
ansible-playbook -i inventory/hosts.yaml playbooks/deploy-kserve-models.yml
```

### Method 2: Helm Chart

**Advantages:**
- Direct control over deployment
- Easy customization
- Standard Kubernetes workflow

**Steps:**

1. Deploy using Helm:

```bash
helm install kserve-llama core/helm-charts/kserve \
  -f core/helm-charts/kserve/xeon-values.yaml \
  --set LLM_MODEL_ID="meta-llama/Llama-3.2-3B-Instruct" \
  --set SERVED_MODEL_NAME="llama-3-2-3b" \
  --namespace default
```

2. Check status:

```bash
kubectl get inferenceservice kserve-llama -n default
```

### Method 3: kubectl Apply

**Advantages:**
- Fine-grained control
- Custom configurations
- GitOps-friendly

**Steps:**

1. Render Helm templates:

```bash
helm template kserve-llama core/helm-charts/kserve \
  -f core/helm-charts/kserve/xeon-values.yaml \
  --set LLM_MODEL_ID="meta-llama/Llama-3.2-3B-Instruct" \
  > kserve-inferenceservice.yaml
```

2. Apply manifests:

```bash
kubectl apply -f kserve-inferenceservice.yaml
```

## Platform-Specific Deployment

### Deploying on Intel Xeon

**Configuration:**

```yaml
# inference_kserve.yml
kserve_cpu_deployment: true
kserve_platform: "xeon"
kserve_model_name_list:
  - "meta-llama/Llama-3.2-3B-Instruct"
```

**Deployment:**

```bash
ansible-playbook -i inventory/hosts.yaml \
  playbooks/deploy-kserve-models.yml \
  --tags "deploy,xeon,cpu"
```

**Optimization Tips:**
- Use AVX512-enabled Xeon processors for best performance
- Enable CPU pinning for consistent latency
- Configure appropriate tensor parallel size based on CPU cores
- Use NRI CPU Balloons for resource optimization (if deployed)

### Deploying on Intel Gaudi

**Prerequisites:**
- Habana AI operator installed
- Gaudi drivers and firmware up to date

**Configuration:**

```yaml
# inference_kserve.yml
kserve_gpu_deployment: true
kserve_platform: "gaudi"  # or "gaudi3"
kserve_model_name_list:
  - "meta-llama/Llama-3.1-8B-Instruct"
```

**Deployment:**

```bash
ansible-playbook -i inventory/hosts.yaml \
  playbooks/deploy-kserve-models.yml \
  --tags "deploy,gaudi,gpu"
```

**Optimization Tips:**
- Use tensor parallelism for large models (8B+)
- Enable bfloat16 precision for better throughput
- Configure appropriate batch sizes for Gaudi memory
- Use enforce-eager mode for consistent performance

## Accessing Models

### Using curl

```bash
# Get InferenceService URL
ISVC_URL=$(kubectl get inferenceservice kserve-llama -n default -o jsonpath='{.status.url}')

# Send inference request
curl -X POST $ISVC_URL/v1/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "llama-3-2-3b",
    "prompt": "What is artificial intelligence?",
    "max_tokens": 100
  }'
```

### Using Python

```python
import openai

# Configure OpenAI client
openai.api_base = "http://kserve-llama.default.svc.cluster.local/v1"
openai.api_key = "not-needed"

# Send request
response = openai.Completion.create(
    model="llama-3-2-3b",
    prompt="What is artificial intelligence?",
    max_tokens=100
)

print(response.choices[0].text)
```

### Through API Gateway (APISIX)

If APISIX is enabled:

```bash
# Get gateway URL
GATEWAY_URL=$(kubectl get svc genai-gateway -n default -o jsonpath='{.status.loadBalancer.ingress[0].ip}')

# Send request through gateway
curl -X POST http://$GATEWAY_URL/kserve-llama/v1/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "llama-3-2-3b",
    "prompt": "What is artificial intelligence?",
    "max_tokens": 100
  }'
```

## Monitoring and Observability

### Prometheus Metrics

KServe exposes metrics for monitoring:

- Request latency (p50, p95, p99)
- Request throughput (requests/second)
- Model loading time
- Queue depth
- GPU/CPU utilization

**Enable ServiceMonitor:**

```yaml
serviceMonitor:
  enabled: true
  interval: 30s
```

**Access Prometheus:**

```bash
kubectl port-forward -n observability svc/prometheus 9090:9090
```

### Grafana Dashboards

Pre-configured dashboards are available when observability is enabled:

- KServe Model Performance
- Inference Latency Metrics
- Resource Utilization

**Access Grafana:**

```bash
kubectl port-forward -n observability svc/grafana 3000:3000
```

### Logging

**View InferenceService logs:**

```bash
# Predictor logs
kubectl logs -n default -l serving.kserve.io/inferenceservice=kserve-llama

# Follow logs
kubectl logs -n default -l serving.kserve.io/inferenceservice=kserve-llama -f
```

## Troubleshooting

### InferenceService Not Ready

**Check status:**

```bash
kubectl describe inferenceservice kserve-llama -n default
```

**Common issues:**

1. **Insufficient resources:**
   - Check node capacity
   - Adjust resource requests/limits

2. **Image pull errors:**
   - Verify image repository access
   - Check imagePullSecrets

3. **Model download timeout:**
   - Increase storage size
   - Use pre-downloaded models in PVC

### Pod in CrashLoopBackOff

**Check logs:**

```bash
kubectl logs -n default <pod-name>
```

**Common issues:**

1. **OOM (Out of Memory):**
   - Reduce max_model_len
   - Increase memory limits
   - Reduce batch size

2. **CUDA/Gaudi errors:**
   - Verify Gaudi drivers
   - Check resource allocation

3. **Model not found:**
   - Verify HuggingFace token
   - Check model ID spelling

### Slow Inference

**Performance tuning:**

1. **Enable prefix caching:**
   ```yaml
   extraCmdArgs:
     - "--enable-prefix-caching"
   ```

2. **Adjust parallelism:**
   ```yaml
   tensor_parallel_size: 2  # For multi-GPU/Gaudi
   ```

3. **Optimize batch size:**
   ```yaml
   extraCmdArgs:
     - "--max-num-seqs"
     - "256"
   ```

## Advanced Configuration

### Canary Deployment

Deploy a new model version alongside the existing one:

```yaml
apiVersion: serving.kserve.io/v1beta1
kind: InferenceService
metadata:
  name: kserve-llama
spec:
  predictor:
    canaryTrafficPercent: 20  # Route 20% traffic to canary
    ...
```

### Multi-Model Serving

Deploy multiple models in a single service:

```bash
# Deploy multiple models
helm install kserve-llama-3b core/helm-charts/kserve \
  --set LLM_MODEL_ID="meta-llama/Llama-3.2-3B-Instruct"

helm install kserve-qwen-7b core/helm-charts/kserve \
  --set LLM_MODEL_ID="Qwen/Qwen2.5-7B-Instruct"
```

### Custom Runtime Configuration

Create a custom ClusterServingRuntime:

```yaml
apiVersion: serving.kserve.io/v1alpha1
kind: ClusterServingRuntime
metadata:
  name: vllm-custom
spec:
  supportedModelFormats:
    - name: vllm
      version: "1"
  containers:
    - name: kserve-container
      image: your-custom-vllm-image:latest
      command:
        - python3
        - -m
        - vllm.entrypoints.openai.api_server
      args:
        - --model
        - "{{.Name}}"
        - --custom-arg
        - "value"
```

### Integration with GenAI Gateway

Enable GenAI Gateway integration:

```yaml
# In inference_kserve.yml
kserve_apisix_route_enabled: true
deploy_genai_gateway: true
```

This enables:
- Authentication via Keycloak
- Rate limiting
- Request routing
- API management

## Uninstalling

### Uninstall Models

```bash
# Set uninstall flag
# In inference-config.cfg
uninstall_kserve=on

# Run playbook
ansible-playbook -i inventory/hosts.yaml playbooks/deploy-kserve-models.yml --tags uninstall
```

### Uninstall KServe Operator

```bash
ansible-playbook -i inventory/hosts.yaml playbooks/deploy-kserve-operator.yml \
  -e "uninstall_kserve=true"
```

## Best Practices

1. **Resource Planning:**
   - Allocate sufficient memory based on model size (typically 2-3x model size)
   - Use node selectors to ensure models run on appropriate hardware

2. **Security:**
   - Use secrets for HuggingFace tokens
   - Enable mTLS for service-to-service communication
   - Apply network policies to restrict access

3. **Performance:**
   - Enable autoscaling for variable workloads
   - Use prefix caching for common prompts
   - Monitor metrics and adjust configuration iteratively

4. **Operations:**
   - Version your InferenceService manifests
   - Use GitOps for deployment management
   - Implement proper backup for PVC-stored models

## Support and References

- [KServe Documentation](https://kserve.github.io/website/)
- [vLLM Documentation](https://docs.vllm.ai/)
- [Intel Gaudi Documentation](https://docs.habana.ai/)
- Enterprise Inference Repository: [GitHub](https://github.com/opea-project/Enterprise-Inference)

## Related Guides

- [Single Node Deployment](single-node-deployment.md)
- [Multi-Node Deployment](multi-node-deployment.md)
- [Supported Models](supported-models.md)
- [Observability Setup](observability.md)
- [CPU Optimization Guide](cpu-optimization-guide.md)
