# KServe Examples

This directory contains example configurations for deploying LLM inference services using KServe with vLLM backend.

## Files

- **kserve-xeon-config.yml**: Configuration for deploying models on Intel Xeon CPUs
- **kserve-gaudi-config.yml**: Configuration for deploying models on Intel Gaudi AI Accelerators

## Usage

1. Copy the appropriate configuration file to `core/inventory/metadata/vars/inference_kserve.yml`

2. Customize the configuration:
   - Update `kserve_model_name_list` with your desired models
   - Adjust resource allocations based on your hardware
   - Configure storage and networking options

3. Deploy KServe operator:
   ```bash
   cd core
   ansible-playbook -i inventory/hosts.yaml playbooks/deploy-kserve-operator.yml
   ```

4. Deploy models:
   ```bash
   ansible-playbook -i inventory/hosts.yaml playbooks/deploy-kserve-models.yml
   ```

## Quick Start Examples

### Deploy Llama 3.2 3B on Xeon

```bash
# Copy configuration
cp docs/examples/kserve/kserve-xeon-config.yml core/inventory/metadata/vars/inference_kserve.yml

# Deploy
cd core
ansible-playbook -i inventory/hosts.yaml playbooks/deploy-kserve-operator.yml
ansible-playbook -i inventory/hosts.yaml playbooks/deploy-kserve-models.yml
```

### Deploy Llama 3.1 8B on Gaudi

```bash
# Copy configuration
cp docs/examples/kserve/kserve-gaudi-config.yml core/inventory/metadata/vars/inference_kserve.yml

# Deploy
cd core
ansible-playbook -i inventory/hosts.yaml playbooks/deploy-kserve-operator.yml
ansible-playbook -i inventory/hosts.yaml playbooks/deploy-kserve-models.yml
```

## Additional Resources

- [KServe Deployment Guide](../../kserve-deployment-guide.md)
- [Supported Models](../../supported-models.md)
- [Accessing Deployed Models](../../accessing-deployed-models.md)
