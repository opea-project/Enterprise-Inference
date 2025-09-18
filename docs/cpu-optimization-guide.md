# Intel AI for Enterprise Inference - CPU Optimization
 
## Overview
 
The system automatically optimizes CPU allocation for AI models using balloon policy. This happens automatically in the background - no customer configuration required.
 
## Automatic Features
 
### CPU Allocation
- System automatically detects available CPU cores
- Reserves 18% of CPUs for system processes
- Allocates remaining CPUs to AI models
- Assigns dedicated CPU cores to each model

### Memory Allocation
- System automatically detects available memory
- Reserves 18% of memory for system processes
- Allocates remaining memory to AI models
 
### Hardware Detection
- Automatically detects NUMA topology
- Configures optimal parallelism strategy
- Adjusts resource allocation based on hardware
 
## Configuration
 
### Model Requirements
Models must include this label to receive CPU optimization:
```yaml
labels:
  name: vllm
```
 
### Resource Allocation
```yaml
# Example for 48-core system
resources:
  requests:
    cpu: 40        # Automatically calculated
    memory: 4G
```
 
## Recommendations for Single Node Clusters with Limited CPUs

For single node clusters (e.g., systems with 48 CPU cores), only Keycloak and APISIX are supported. GenAI Gateway is not supported on these configurations. To deploy GenAI Gateway, a minimum of 96 CPU cores is required.

**Summary:**
- For clusters with limited CPU resources, deploy only Keycloak and APISIX.
- GenAI Gateway deployment requires at least 96 CPU cores.
 
## Status Verification
 
### Check System Status
```bash
# Verify balloon policy is running
kubectl get pods -n kube-system | grep nri-resource-policy
 
# Check model CPU allocation
kubectl exec <model-pod> -- cat /proc/self/status | grep Cpus_allowed_list
```
 
### Troubleshooting
If models aren't performing optimally:
 
1. Verify balloon policy pod is running
2. Check model pod has `name: vllm` label
3. Confirm CPU allocation in pod status
 
## Summary
 
CPU optimization runs automatically and provides:
- Dedicated CPU cores for each model
- Consistent performance
- Optimal resource utilization