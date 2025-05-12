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
   - **Tensor Parallel Size** (based on available Gaudi cards)

> **Note**: This deploys a model that has **not** been pre-validated. Make sure the tensor parallel size is configured correctly. An incorrect value can result in the model being stuck in a "not ready" state.
