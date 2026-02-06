# KServe Integration for Enterprise Inference

This document provides technical details about the KServe integration with vLLM backend for Intel platforms.

## Architecture Overview

The KServe integration adds a Kubernetes-native model serving layer to Enterprise Inference, providing:

- **Serverless inference**: Automatic scaling to zero when idle
- **Advanced autoscaling**: Scale based on request load and custom metrics  
- **Canary deployments**: Gradual rollout of new model versions
- **Multi-framework support**: Deploy vLLM, TGI, or custom runtimes
- **Built-in monitoring**: Prometheus metrics and observability integration

## Components

### 1. Helm Chart (`core/helm-charts/kserve/`)

The KServe Helm chart provides a declarative way to deploy InferenceServices with vLLM runtime.

**Key files:**
- `Chart.yaml`: Chart metadata
- `values.yaml`: Default configuration values
- `xeon-values.yaml`: Intel Xeon CPU optimizations
- `gaudi-values.yaml`: Intel Gaudi accelerator optimizations
- `gaudi3-values.yaml`: Intel Gaudi3 accelerator optimizations

**Templates:**
- `inferenceservice.yaml`: Main KServe InferenceService resource
- `pvc.yaml`: PersistentVolumeClaim for model storage
- `configmap.yaml`: Configuration for vLLM runtime
- `service.yaml`: Kubernetes Service
- `ingress.yaml`: Ingress configuration
- `apisixroute.yaml`: APISIX API gateway route
- `servicemonitor.yaml`: Prometheus ServiceMonitor

### 2. Ansible Playbooks

#### `deploy-kserve-operator.yml`

Installs and configures the KServe operator with Intel-optimized runtimes.

**Features:**
- Installs KServe CRDs and controller
- Creates Intel-optimized ClusterServingRuntimes for vLLM
- Supports Xeon and Gaudi platforms
- Handles operator uninstallation

**Usage:**
```bash
ansible-playbook -i inventory/hosts.yaml playbooks/deploy-kserve-operator.yml
```

**Variables:**
- `install_kserve`: Install KServe operator (default: false)
- `uninstall_kserve`: Uninstall KServe operator (default: false)
- `kserve_version`: KServe version to install (default: "0.13.0")
- `configure_intel_runtimes`: Create Intel-optimized runtimes (default: true)

#### `deploy-kserve-models.yml`

Deploys LLM models using KServe InferenceServices.

**Features:**
- Platform-specific deployments (Xeon, Gaudi, Gaudi3)
- Helm-based model deployment
- HuggingFace token validation
- Model lifecycle management (deploy, list, uninstall)

**Usage:**
```bash
ansible-playbook -i inventory/hosts.yaml playbooks/deploy-kserve-models.yml
```

**Variables:**
- `kserve_model_name_list`: List of models to deploy
- `kserve_platform`: Target platform (xeon, gaudi, gaudi3)
- `kserve_cpu_deployment`: Enable CPU deployment
- `kserve_gpu_deployment`: Enable Gaudi deployment

### 3. Configuration Files

#### `inventory/metadata/vars/inference_kserve.yml`

Central configuration file for KServe deployments.

**Key sections:**
- Operator settings (version, installation flags)
- Model deployment settings (platform, backend, method)
- Storage configuration (PVC size, storage class)
- Autoscaling configuration (min/max replicas, targets)
- Monitoring configuration (ServiceMonitor)
- Network configuration (Ingress, APISIX)

#### `inventory/inference-config.cfg`

Main configuration file with KServe deployment toggles:
- `deploy_kserve_operator`: Install KServe operator
- `deploy_kserve_models`: Deploy models with KServe
- `uninstall_kserve`: Uninstall KServe components

## Deployment Flow

### Initial Setup

1. **Install KServe Operator**
   ```bash
   # Set in inference-config.cfg
   deploy_kserve_operator=on
   
   # Run playbook
   ansible-playbook -i inventory/hosts.yaml playbooks/deploy-kserve-operator.yml
   ```

2. **Configure Model Deployment**
   ```yaml
   # In inventory/metadata/vars/inference_kserve.yml
   kserve_cpu_deployment: true
   kserve_platform: "xeon"
   kserve_model_name_list:
     - "meta-llama/Llama-3.2-3B-Instruct"
   ```

3. **Deploy Models**
   ```bash
   ansible-playbook -i inventory/hosts.yaml playbooks/deploy-kserve-models.yml
   ```

### Platform-Specific Deployment

#### Intel Xeon
```yaml
kserve_cpu_deployment: true
kserve_platform: "xeon"
```

Resources:
- CPU: 16-32 cores
- Memory: 64-128GB
- Node selector: AVX512VNNI support

#### Intel Gaudi
```yaml
kserve_gpu_deployment: true
kserve_platform: "gaudi"
```

Resources:
- Gaudi accelerators: 1
- CPU: 16-32 cores
- Memory: 128-256GB
- Node selector: gaudi instance type

#### Intel Gaudi3
```yaml
kserve_gpu_deployment: true
kserve_platform: "gaudi3"
```

Resources:
- Gaudi3 accelerators: 1
- CPU: 24-48 cores
- Memory: 256-512GB
- Node selector: gaudi3 instance type

## Integration with Existing Components

### Observability Stack

KServe integrates with the existing observability components:

- **Prometheus**: Metrics collection via ServiceMonitor
- **Grafana**: Visualization of inference metrics
- **Loki**: Log aggregation for InferenceService pods

Enable with:
```yaml
kserve_service_monitor_enabled: true
```

### API Gateway (APISIX)

Route traffic through APISIX for:
- Authentication (Keycloak integration)
- Rate limiting
- Request routing
- API management

Enable with:
```yaml
kserve_apisix_route_enabled: true
```

### GenAI Gateway

KServe models can be registered with GenAI Gateway for:
- Unified API interface
- Token management
- User analytics
- Multi-model routing

## Development Guide

### Adding a New Platform

1. Create a new values file: `<platform>-values.yaml`
2. Define platform-specific configurations:
   - Image repository and tag
   - Resource allocations
   - Node selectors and tolerations
   - Model configurations

3. Update `deploy-kserve-models.yml` to support the platform:
   - Add platform-specific deployment block
   - Set appropriate values file path
   - Configure platform-specific tags

### Customizing Model Configurations

Add model-specific configurations in `inference_kserve.yml`:

```yaml
kserve_model_configs:
  "meta-llama/Llama-3.2-3B-Instruct":
    tensor_parallel_size: 1
    pipeline_parallel_size: 1
    extraCmdArgs:
      - "--disable-log-requests"
      - "--enable-prefix-caching"
      - "--max-num-seqs"
      - "128"
```

### Creating Custom Runtimes

Create a ClusterServingRuntime in `deploy-kserve-operator.yml`:

```yaml
- name: Create custom ClusterServingRuntime
  kubernetes.core.k8s:
    state: present
    definition:
      apiVersion: serving.kserve.io/v1alpha1
      kind: ClusterServingRuntime
      metadata:
        name: custom-runtime
      spec:
        supportedModelFormats:
          - name: custom
            version: "1"
        containers:
          - name: kserve-container
            image: your-custom-image:latest
            ...
```

## Testing

### Unit Tests

Test Helm chart rendering:
```bash
helm lint core/helm-charts/kserve
helm template test core/helm-charts/kserve -f core/helm-charts/kserve/xeon-values.yaml
```

### Integration Tests

Deploy a test model:
```bash
helm install test-model core/helm-charts/kserve \
  -f core/helm-charts/kserve/xeon-values.yaml \
  --set LLM_MODEL_ID="meta-llama/Llama-3.2-3B-Instruct" \
  --namespace test
```

Verify deployment:
```bash
kubectl get inferenceservice -n test
kubectl logs -n test -l serving.kserve.io/inferenceservice=test-model
```

### End-to-End Tests

Run inference request:
```bash
ISVC_URL=$(kubectl get inferenceservice test-model -n test -o jsonpath='{.status.url}')
curl -X POST $ISVC_URL/v1/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "llama-3-2-3b", "prompt": "Hello", "max_tokens": 10}'
```

## Troubleshooting

### Common Issues

**Issue: InferenceService not ready**
- Check: `kubectl describe inferenceservice <name>`
- Verify: Resource availability, image pull, model download
- Logs: `kubectl logs -l serving.kserve.io/inferenceservice=<name>`

**Issue: Model download timeout**
- Increase PVC size
- Verify HuggingFace token
- Check network connectivity

**Issue: OOM (Out of Memory)**
- Reduce `max_model_len`
- Increase memory limits
- Reduce batch size settings

### Debug Mode

Enable verbose logging:
```yaml
extraCmdArgs:
  - "--log-level"
  - "debug"
```

## Security Considerations

### Capabilities for Gaudi

Gaudi deployments require specific Linux capabilities:
- `SYS_PTRACE`: Required for Habana profiler and debugging
- `IPC_LOCK`: Required for locking memory for DMA operations
- `SYS_NICE`: Required for process priority management

These are documented in the values files and should only be used for Gaudi deployments.

### Network Security

- Use `NetworkPolicy` to restrict traffic
- Enable mTLS with Istio integration
- Use Keycloak for authentication
- Apply RBAC for resource access

## Performance Tuning

### Xeon Optimization
- Enable AVX512 instructions
- Use CPU pinning for consistency
- Configure appropriate parallelism settings
- Enable prefix caching for repeated prompts

### Gaudi Optimization
- Use bfloat16 precision
- Enable enforce-eager mode
- Configure optimal batch sizes
- Use tensor parallelism for large models

## Future Enhancements

Planned improvements:
- [ ] Support for additional backends (TGI, custom)
- [ ] Multi-model serving with single InferenceService
- [ ] Advanced autoscaling with custom metrics
- [ ] A/B testing and traffic splitting
- [ ] Model versioning and rollback
- [ ] Integration with model registries (MLflow, etc.)

## Contributing

When adding new features:
1. Update Helm chart and templates
2. Add/update Ansible playbooks
3. Update documentation
4. Add examples
5. Test on target platforms
6. Submit PR with detailed description

## References

- [KServe Documentation](https://kserve.github.io/website/)
- [vLLM Documentation](https://docs.vllm.ai/)
- [Intel Gaudi Documentation](https://docs.habana.ai/)
- [Helm Documentation](https://helm.sh/docs/)
- [Ansible Documentation](https://docs.ansible.com/)
