# Intel AI for Enterprise Inference - CPU Optimization
 
## Overview
 
The system automatically optimizes CPU allocation for AI models using balloon policy. This happens automatically in the background - no customer configuration required.
 
## Automatic Features
 
### CPU Allocation

**System CPU Reservation**: A total of **8 vCPUs** is reserved for infrastructure components (Keycloak, APISIX, observability, kube-system), distributed evenly across NUMA nodes.

**Intelligent CPU Selection**:
- Automatically detects NUMA topology and hyperthreading configuration
- For hyperthreaded systems: Balances reservations between physical cores and HT siblings
  - Example (48 cores with HT): Reserves from both physical cores (0-23) and HT cores (24-47)
- For non-segmented CPUs (e.g., "0-47"): Creates virtual segments at the midpoint
- For segmented CPUs (e.g., "0-23,48-71"): Uses existing segment boundaries

**Model CPU Allocation**:
- Remaining CPUs (after reservation) are allocated to LLM models
- Assigns dedicated CPU cores to each model for optimal performance
 
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
    # for tp1, tp2 system should have minimum 128Gi and for tp>=4 minimum 256Gi memory available for the model's pod
    memory: 128Gi  
```
 
## System Component Deployment Recommendations

For single-node Xeon clusters, **Keycloak** and **APISIX** are recommended.

For Gaudi or large multi-node Xeon clusters, the GenAI Gateway is well-suited.

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