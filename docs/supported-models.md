### Xeon and Gaudi Supported Models

The following table lists the pre-validated models for Intel® AI for Enterprise Inference.

**Deployment Backends:**
- **vLLM**: Default backend for LLM inference (direct Kubernetes deployment)
- **TGI**: Text Generation Inference (direct Kubernetes deployment)
- **KServe**: Kubernetes-native model serving with autoscaling and serverless capabilities
- **OVMS**: OpenVINO Model Server for optimized Intel CPU/GPU inference
- **TEI**: Text Embeddings Inference for embedding models

### ✅ **Model Support Matrix**

 **Model**                                                                                  | **Xeon** | **Gaudi** |
---------------------------------------------------------------------------------------------|:-------------------:|:---------------------:|
[**deepseek-ai/DeepSeek-R1-Distill-Qwen-32B**](https://huggingface.co/deepseek-ai/DeepSeek-R1-Distill-Qwen-32B) | ✓              | ✓                    |
[**deepseek-ai/DeepSeek-R1-Distill-Llama-8B**](https://huggingface.co/deepseek-ai/DeepSeek-R1-Distill-Llama-8B) | ✓           | ✓                   |
[**meta-llama/Llama-3.1-8B-Instruct**](https://huggingface.co/meta-llama/Llama-3.1-8B-Instruct)                   | ✓ | ✓                    |
[**meta-llama/Llama-3.2-3B-Instruct**](https://huggingface.co/meta-llama/Llama-3.2-3B-Instruct)                   | ✓ |                     |
[**Qwen/Qwen3-1.7B**](https://huggingface.co/Qwen/Qwen3-1.7B)                   | ✓ |                     |
[**Qwen/Qwen3-4B-Instruct-2507**](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507)                   | ✓ |                     |
[**meta-llama/Llama-3.1-70B-Instruct**](https://huggingface.co/meta-llama/Llama-3.1-70B-Instruct)                |                     | ✓                    |
[**meta-llama/Llama-3.1-405B-Instruct**](https://huggingface.co/meta-llama/Llama-3.1-405B-Instruct)             |                     | ✓ (Gaudi3)                      | ✓ 
[**meta-llama/Llama-4-Scout-17B-16E-Instruct**](https://huggingface.co/meta-llama/Llama-4-Scout-17B-16E-Instruct)             |                     | ✓                      | ✓ 
[**Qwen/Qwen2.5-32B-Instruct**](https://huggingface.co/Qwen/Qwen2.5-32B-Instruct)             |                     | ✓                      | ✓ 
[**mistralai/Mixtral-8x7B-Instruct-v0.1**](https://huggingface.co/mistralai/Mixtral-8x7B-Instruct-v0.1)          |                     | ✓                    |
[**mistralai/Mistral-7B-Instruct-v0.3**](https://huggingface.co/mistralai/Mistral-7B-Instruct-v0.3)              |                     | ✓                    |
[**BAAI/bge-reranker-base**](https://huggingface.co/BAAI/bge-reranker-base)             |                     | ✓  
[**BAAI/bge-base-en-v1.5**](https://huggingface.co/BAAI/bge-base-en-v1.5)             |  | ✓

