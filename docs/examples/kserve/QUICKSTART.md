# Quick Start: KServe with vLLM on Intel Platforms

This guide provides the fastest path to deploying LLM models with KServe on Intel hardware.

## Prerequisites

- Kubernetes cluster (1.24+) or OpenShift (4.12+)
- kubectl configured
- Helm 3.x installed
- Ansible 2.14+ on deployment machine
- Intel Xeon (3rd Gen+) or Intel Gaudi accelerators

## 5-Minute Setup

### Step 1: Install KServe Operator

```bash
cd /path/to/Enterprise-Inference/core

# Edit configuration
vim inventory/inference-config.cfg
# Set: deploy_kserve_operator=on

# Install operator
ansible-playbook -i inventory/hosts.yaml playbooks/deploy-kserve-operator.yml
```

Expected output:
```
TASK [Display KServe installation result] ******
ok: [node1] => {
    "msg": "KServe controller is running"
}
```

### Step 2: Configure Model Deployment

**For Intel Xeon:**
```bash
# Copy example configuration
cp docs/examples/kserve/kserve-xeon-config.yml inventory/metadata/vars/inference_kserve.yml

# Edit to customize
vim inventory/metadata/vars/inference_kserve.yml
```

**For Intel Gaudi:**
```bash
# Copy example configuration
cp docs/examples/kserve/kserve-gaudi-config.yml inventory/metadata/vars/inference_kserve.yml

# Edit to customize
vim inventory/metadata/vars/inference_kserve.yml
```

### Step 3: Set HuggingFace Token

```bash
# Edit vault configuration
vim inventory/metadata/vars/vault.yml

# Add your token
hugging_face_token: "hf_your_token_here"
```

### Step 4: Deploy Model

```bash
# Deploy models
ansible-playbook -i inventory/hosts.yaml playbooks/deploy-kserve-models.yml
```

Wait for model to be ready:
```bash
kubectl get inferenceservice
```

Expected output:
```
NAME                              URL                                              READY
kserve-meta-llama-llama-3-2-3b   http://kserve-meta-llama-llama-3-2-3b.default   True
```

### Step 5: Test Inference

Get the service URL:
```bash
ISVC_URL=$(kubectl get inferenceservice kserve-meta-llama-llama-3-2-3b -o jsonpath='{.status.url}')
```

Send a test request:
```bash
curl -X POST $ISVC_URL/v1/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "llama-3-2-3b",
    "prompt": "What is Kubernetes?",
    "max_tokens": 100,
    "temperature": 0.7
  }'
```

## Alternative: Direct Helm Deployment

If you prefer using Helm directly:

```bash
# For Xeon
helm install my-model core/helm-charts/kserve \
  -f core/helm-charts/kserve/xeon-values.yaml \
  --set LLM_MODEL_ID="meta-llama/Llama-3.2-3B-Instruct" \
  --set SERVED_MODEL_NAME="llama-3-2-3b"

# For Gaudi
helm install my-model core/helm-charts/kserve \
  -f core/helm-charts/kserve/gaudi-values.yaml \
  --set LLM_MODEL_ID="meta-llama/Llama-3.1-8B-Instruct" \
  --set SERVED_MODEL_NAME="llama-3-1-8b"
```

## Verify Deployment

### Check InferenceService Status

```bash
kubectl get inferenceservice
kubectl describe inferenceservice <name>
```

### Check Pods

```bash
kubectl get pods -l serving.kserve.io/inferenceservice=<name>
kubectl logs -l serving.kserve.io/inferenceservice=<name> -f
```

### Check Resources

```bash
kubectl get all -l app.kubernetes.io/instance=<release-name>
```

## Common Customizations

### Change Model

Edit `inventory/metadata/vars/inference_kserve.yml`:
```yaml
kserve_model_name_list:
  - "Qwen/Qwen2.5-7B-Instruct"
  - "microsoft/Phi-3-mini-4k-instruct"
```

### Enable Autoscaling

```yaml
kserve_autoscaling_enabled: true
kserve_autoscaling_min_replicas: 1
kserve_autoscaling_max_replicas: 4
```

### Enable Monitoring

```yaml
kserve_service_monitor_enabled: true
```

### Enable API Gateway

```yaml
kserve_apisix_route_enabled: true
```

## Access Patterns

### Direct Service Access
```bash
kubectl port-forward svc/<service-name> 8080:80
curl http://localhost:8080/v1/completions ...
```

### Through Ingress
```bash
# Get ingress IP
kubectl get ingress

# Access via ingress
curl http://<ingress-ip>/<path>/v1/completions ...
```

### Through APISIX Gateway
```bash
# Get gateway service
kubectl get svc genai-gateway

# Access via gateway
curl http://<gateway-ip>/<model-path>/v1/completions ...
```

## Troubleshooting Quick Fixes

### Model Download Timeout
```bash
# Increase PVC size
kubectl patch pvc <pvc-name> -p '{"spec":{"resources":{"requests":{"storage":"200Gi"}}}}'
```

### Out of Memory
```bash
# Edit deployment to reduce max_model_len
helm upgrade <release> core/helm-charts/kserve \
  --reuse-values \
  --set max_model_len=2048
```

### Check Logs
```bash
# Controller logs
kubectl logs -n kserve -l control-plane=kserve-controller-manager

# Inference logs
kubectl logs -l serving.kserve.io/inferenceservice=<name> --tail=100
```

## Cleanup

### Uninstall Model
```bash
helm uninstall <release-name>
# OR
ansible-playbook -i inventory/hosts.yaml playbooks/deploy-kserve-models.yml \
  -e "uninstall_kserve=true"
```

### Uninstall Operator
```bash
ansible-playbook -i inventory/hosts.yaml playbooks/deploy-kserve-operator.yml \
  -e "uninstall_kserve=true"
```

## Next Steps

- Read the [full deployment guide](../../docs/kserve-deployment-guide.md)
- Explore [example configurations](../../docs/examples/kserve/)
- Check [supported models](../../docs/supported-models.md)
- Set up [observability](../../docs/observability.md)

## Getting Help

- Check logs: `kubectl logs -l serving.kserve.io/inferenceservice=<name>`
- Describe resource: `kubectl describe inferenceservice <name>`
- Review [troubleshooting guide](../../docs/kserve-deployment-guide.md#troubleshooting)
- Open an [issue](https://github.com/opea-project/Enterprise-Inference/issues)
