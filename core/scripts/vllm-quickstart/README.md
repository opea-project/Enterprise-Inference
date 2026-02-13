## 📋 Overview

The `vllm-model-runner.sh` launcher script simplifies the deployment of popular open-source LLMs with optimized configurations for CPU-based inference. It handles dependency installation, hardware detection, Docker container management, and health monitoring automatically.

## ✨ Features

- **One-Command Deployment** — Interactive model selection and automated setup
- **Multi-Model Support** — Pre-configured profiles for popular LLMs
- **Custom Port Configuration** — Run the server on any port with `-p` option
- **Hardware Auto-Detection** — Automatically configures tensor/pipeline parallelism based on NUMA topology
- **Dependency Management** — Installs Docker, jq, curl, and git if missing
- **Container Lifecycle Management** — Gracefully handles existing containers
- **Health Monitoring** — Built-in health checks with detailed logging
- **Tool Calling Support** — Pre-configured for function/tool calling capabilities

## 📦 Prerequisites

- **Operating System**: Ubuntu
- **HuggingFace Token**: Required for downloading models
- **Sudo Access**: Required for dependency installation
- **Hardware**: CPU with sufficient RAM for model inference

> **Note:** The script will automatically install Docker, jq, curl, and git if they are not present.

## 🛠️ Installation

1. **Set your HuggingFace token:**
   ```bash
   export HFToken="your_huggingface_token_here"
   ```

2. **Make the script executable:**
   ```bash
   chmod +x vllm-model-runner.sh
   ```

## 🎯 Usage

### Quick Start

```bash
./vllm-model-runner.sh
```

To run on a custom port:

```bash
./vllm-model-runner.sh -p 8080
# or
./vllm-model-runner.sh --port 8080
```

The script will:
1. Check and install any missing dependencies
2. Validate your environment and HuggingFace token
3. Display available models for selection
4. Detect hardware configuration for optimal parallelism
5. Pull the vLLM Docker image (if not cached)
6. Start the vLLM server container
7. Perform health checks until the server is ready

### Example Session

```
[INFO] Starting vLLM Model Launcher
[INFO] Server will run on port: 8000
[INFO] Checking and installing prerequisites...
[SUCCESS] All prerequisites are satisfied

Available Models:

 1) Llama 3.1 8B Instruct
 2) Qwen 3 14B
 3) Mistral 7B Instruct v0.3

Enter the number of the model you want to start:
> 1

[INFO] User selected model: llama-8B
[INFO] Starting vLLM container for model: llama-8B
[SUCCESS] vLLM server is running successfully at http://localhost:8000/health
✅ vLLM server is running successfully at http://localhost:8000/health
```

### API Endpoints

Once running, the vLLM server exposes an OpenAI-compatible API (replace `8000` with your custom port if specified):

| Endpoint | Description |
|----------|-------------|
| `http://localhost:8000/health` | Health check endpoint |
| `http://localhost:8000/v1/chat/completions` | Chat completions API |
| `http://localhost:8000/v1/completions` | Text completions API |
| `http://localhost:8000/v1/models` | List available models |

### Example API Call

```bash
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "meta-llama/Llama-3.1-8B-Instruct",
    "messages": [
      {"role": "user", "content": "Hello, how are you?"}
    ],
    "max_tokens": 100
  }'
```

## ⚙️ Configuration

### models.json Structure

The `models.json` file contains all configuration:

```json
{
  "docker": {
    "image": "public.ecr.aws/q9t5s3a7/vllm-cpu-release-repo:v0.11.2",
    "port": "8000:8000",
    "environment": { ... },
    "volumes": [ ... ]
  },
  "global_defaults": {
    "block_size": 128,
    "dtype": "bfloat16",
    "trust_remote_code": true,
    ...
  },
  "models": {
    "model-key": {
      "display_name": "Human Readable Name",
      "model_path": "org/model-name",
      "vllm_args": { ... }
    }
  }
}
```

### Adding a New Model

Add a new entry under the `models` section in `models.json`:

```json
"my-model": {
  "display_name": "My Custom Model",
  "model_path": "organization/model-name",
  "vllm_args": {
    "max_model_len": 8192,
    "tool_call_parser": "hermes"
  }
}
```

## 📁 Project Structure

```
.
├── README.md               # This file
├── models.json             # Model configurations and Docker settings
└── vllm-model-runner.sh    # Main launcher script
```

## 🔧 Troubleshooting

### View Logs

```bash
# Startup logs
cat /tmp/vllm-startup.log

# Container logs
docker logs vllm-container

# Follow container logs in real-time
docker logs -f vllm-container
```

### Common Issues

| Issue | Solution |
|-------|----------|
| `HFToken is not set` | Export your HuggingFace token: `export HFToken="hf_..."` |
| `Docker daemon not running` | Start Docker: `sudo systemctl start docker` |
| `Permission denied` | Add user to docker group: `sudo usermod -aG docker $USER` then logout/login |
| `Container keeps stopping` | Check logs: `docker logs vllm-container` — usually indicates insufficient memory |
| `Health check timeout` | Model loading can take several minutes; check logs for progress |

### Stop the Server

```bash
docker stop vllm-container
docker rm vllm-container
```
