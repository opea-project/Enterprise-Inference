# llama.cpp — Intel oneAPI with VMWare Foundation

Runs [llama.cpp](https://github.com/ggml-org/llama.cpp) `llama-server` built with Intel oneAPI compilers and oneMKL BLAS for optimized CPU inference.

## Build & Run

**1. Build the image** (output logged to `$HOME/logs/docker-build.log`):

```bash
mkdir -p $HOME/logs
sudo docker build -f Dockerfile-llamacpp -t llamacpp-intel:latest . \
  2>&1 | tee $HOME/logs/docker-build.log
```

**2. Stop any existing container, then start a fresh one:**

```bash
sudo docker stop llamacpp 2>/dev/null || true

sudo docker run --rm -d \
  --ipc=host --net=host \
  -v $HOME/models:/root/.cache/huggingface \
  -v $HOME/logs:/logs \
  --workdir /workspace \
  --name llamacpp \
  llamacpp-intel:latest \
  --hf-repo win10/DeepSeek-Coder-V2-Lite-Instruct-Q8_0-GGUF \
  --hf-file deepseek-coder-v2-lite-instruct-q8_0.gguf
```

- `--hf-repo` / `--hf-file` — HuggingFace model to serve (swap to use a different model)
- Models are cached in `$HOME/models` — downloaded once, reused on subsequent runs
- Build logs: `$HOME/logs/docker-build.log`
- Server logs: `$HOME/logs/llama-server.log`
- Server listens on `http://localhost:8080`

## Test

```bash
curl http://localhost:8080/v1/completions \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"model": "win10/DeepSeek-Coder-V2-Lite-Instruct-Q8_0-GGUF", "prompt": "What is Deep Learning?", "max_tokens": 25, "temperature": 0}'
```

## Stop

```bash
sudo docker stop llamacpp
```
