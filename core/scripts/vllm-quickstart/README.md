## 📋 Overview

The `vllm-model-runner.sh` launcher script simplifies the deployment of popular open-source LLMs with optimized configurations for both CPU and Intel GPU/XPU inference. It handles dependency installation, hardware detection, Docker container management, and health monitoring automatically.

## ✨ Features

- **One-Command Deployment** — Interactive model selection and automated setup
- **Multi-Model Support** — Pre-configured profiles for popular LLMs
- **Dual Runtime Support** — Switch between CPU and Intel XPU profiles with `--runtime`
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
- **Hardware**:
  - CPU runtime: Intel Xeon class CPU with sufficient RAM
  - XPU runtime: Intel GPU (for example Battlemage/BMG) with `/dev/dri` available on host

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

To explicitly choose runtime:

```bash
./vllm-model-runner.sh --runtime cpu
./vllm-model-runner.sh --runtime xpu
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
3. Resolve the runtime profile (`cpu` or `xpu`)
4. Display available models for selection
5. Detect hardware configuration for optimal parallelism
6. Pull the vLLM Docker image (if not cached)
7. Start the vLLM server container
8. Perform health checks until the server is ready

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
    "default_runtime": "cpu",
    "runtime_profiles": {
      "cpu": {
        "image": "public.ecr.aws/q9t5s3a7/vllm-cpu-release-repo:v0.11.2"
      },
      "xpu": {
        "image": "intel/vllm:0.14.1-xpu"
      }
    },
    "port": "8000:8000",
    "environment": { ... },
    "volumes": [ ... ]
  },
  "global_defaults": {
    "cpu": { ... },
    "xpu": { ... }
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
| `XPU runtime fails to start` | Ensure Intel GPU drivers are installed and `/dev/dri/renderD*` exists on host |

### Stop the Server

```bash
docker stop vllm-container
docker rm vllm-container
```
