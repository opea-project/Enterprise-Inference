### Deploy LLM Model from Hugging Face

This option allows you to deploy any Hugging Face-hosted LLM on the Inference Cluster using its model ID.

**To deploy:**

1. Run the deployment script:
   ```bash
   bash ~/core/inference-stack-deploy.sh
   ```

2. Choose the following options from the menu:
   - `3` – Update Deployed Inference Cluster  
   - `2` – Manage LLM Models  
   - `4` – Deploy Model from Hugging Face

3. When prompted, provide:
   - **Hugging Face Model ID** (e.g., `meta-llama/Meta-Llama-3-8B`)  
   - **Model Deployment Name** (e.g., `metallama-8b`)  
   - **Tensor Parallel Size** (based on available  Intel® AI Accelerator cards)

> **Note**: This deploys a model that has **not** been pre-validated. Make sure the tensor parallel size is configured correctly. An incorrect value can result in the model being stuck in a "not ready" state.

### Customizing Environment Variables and vLLM Arguments

Models deployed from Hugging Face use the `defaultModelConfigs` settings in `core/helm-charts/vllm/xeon-values.yaml`. You can customize environment variables and vLLM command-line arguments by editing the `defaultModelConfigs` section of that file before deploying.

**Example: enabling the SGL kernel, configuring KV cache, and other environment variables**

```yaml
defaultModelConfigs:
  configMapValues:
    VLLM_CPU_SGL_KERNEL: "1"       # Enable the SGL kernel for improved CPU performance
    VLLM_CPU_KVCACHE_SPACE: "40"   # KV cache memory allocation in GB
    # Add or override any other environment variables here
  extraCmdArgs:
    [
      "--block-size", "128",
      "--dtype", "bfloat16",
      "--max-model-len", "8192",
      # Add or override any vLLM CLI arguments here
    ]
```

You can set any vLLM-supported environment variable under `configMapValues` and any vLLM CLI flag under `extraCmdArgs`.
