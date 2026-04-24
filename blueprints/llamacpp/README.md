# llama.cpp — Intel oneAPI with VMWare Foundation

Runs [llama.cpp](https://github.com/ggml-org/llama.cpp) `llama-server` built with Intel oneAPI compilers and oneMKL BLAS for optimized CPU inference.

> **Note:** You can use any GGUF model from Hugging Face. The examples below use specific models, but you can replace them with any GGUF model by setting the appropriate environment variables.

## Build & Run

**1. Build the image** (output logged to `$HOME/logs/docker-build.log`):

```bash
mkdir -p $HOME/logs
sudo docker build -f Dockerfile-llamacpp -t llamacpp-intel:latest . \
  2>&1 | tee $HOME/logs/docker-build.log
```

**2. Set environment variables for your model:**

```bash
# Example 1: Gemma 3 1B IT (default)
export MODEL_REPO="unsloth/gemma-3-1b-it-GGUF"
export MODEL_FILE="gemma-3-1b-it-Q4_K_M.gguf"
export MODEL_NAME="gemma-3-1b-it"

# Example 2: Gemma 3 4B IT
# export MODEL_REPO="google/gemma-2-2b-it-GGUF"
# export MODEL_FILE="gemma-2-2b-it-Q8_0.gguf"
# export MODEL_NAME="gemma-3-4b-it"

# Example 3: Any other GGUF model from Hugging Face
# export MODEL_REPO="<huggingface-username>/<repo-name>"
# export MODEL_FILE="<model-filename>.gguf"
# export MODEL_NAME="<model-name>"
```

**3. Stop any existing container, then start a fresh one:**

```bash
sudo docker stop llamacpp 2>/dev/null || true

sudo docker run --rm -d \
  --ipc=host --net=host \
  -v $HOME/models:/root/.cache/huggingface \
  -v $HOME/logs:/logs \
  --workdir /workspace \
  --name llamacpp \
  llamacpp-intel:latest \
  --hf-repo ${MODEL_REPO} \
  --hf-file ${MODEL_FILE}
```

- `MODEL_REPO` — HuggingFace repository containing the GGUF model
- `MODEL_FILE` — GGUF model file name
- `MODEL_NAME` — Model name for API requests
- Models are cached in `$HOME/models` — downloaded once, reused on subsequent runs
- Build logs: `$HOME/logs/docker-build.log`
- Server logs: `$HOME/logs/llama-server.log`
- Server listens on `http://localhost:8080`

## Test

### Completions API

```bash
curl http://localhost:8080/v1/completions \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"model": "'"${MODEL_NAME}"'", "prompt": "What is Deep Learning?", "max_tokens": 25, "temperature": 0}'
```

### Chat Completions API

```bash
# Set BASE_URL and TOKEN (if using with the gateway)
export BASE_URL="http://localhost:8080"
export TOKEN="your-token-here"  # or leave empty if no auth

curl -k ${BASE_URL}/v1/chat/completions -X POST \
  -d '{
    "model": "'"${MODEL_NAME}"'",
    "messages": [
      {"role": "user", "content": "What is Deep Learning?"}
    ],
    "max_tokens": 25,
    "temperature": 0
  }' \
  -H 'Content-Type: application/json'
```

**Example with Gemma 3 1B IT:**

```bash
export MODEL_NAME="gemma-3-1b-it"

curl -k ${BASE_URL}/v1/chat/completions -X POST \
  -d '{
    "model": "'"${MODEL_NAME}"'",
    "messages": [
      {"role": "user", "content": "What is Deep Learning?"}
    ],
    "max_tokens": 25,
    "temperature": 0
  }' \
  -H 'Content-Type: application/json'
```

## Stop

```bash
sudo docker stop llamacpp
```
