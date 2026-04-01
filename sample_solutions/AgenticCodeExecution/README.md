# MCP Agent Servers

Two-server MCP architecture for code-execution agents:
- a tools server (domain APIs)
- a sandbox server (`execute_python` with `actions.*` proxy)

The repo supports **retail**, **airline**, **stocks**, **banking**, and **triage** domains and is designed for Flowise/custom MCP clients.

## Repository Layout

```
mcp-agent-servers/
├── tools-server/
│   ├── mcp_retail_server.py
│   ├── mcp_airline_server.py
│   ├── mcp_stocks_server.py
│   ├── mcp_banking_server.py
│   ├── mcp_triage_server.py
│   ├── error_hints.py
│   └── session_dbs/
├── sandbox-server/
│   ├── mcp_server_codemode.py
│   ├── execute_python_description.txt
│   └── session_hashes/
├── system-prompts/
│   ├── retail-system-prompt.txt
│   ├── airline-system-prompt.txt
│   ├── stocks-system-prompt.txt
│   ├── banking-system-prompt.txt
│   ├── triage-system-prompt.txt
│   └── tau2-default-system-prompt.txt
└── start_all.sh
```

## Architecture

```
Flowise (or other MCP client)
        └── Custom MCP → sandbox-server (port 5051)
                                                 │ execute_python
                                                 │
                                                 └── MCP client → tools-server (port 5050)
                                                                                             └── retail OR airline OR stocks OR banking OR triage tools
```

## Servers

### tools-server (port 5050)
- Retail domain entrypoint: `tools-server/mcp_retail_server.py`
- Airline domain entrypoint: `tools-server/mcp_airline_server.py`
- Stocks domain entrypoint: `tools-server/mcp_stocks_server.py`
- Banking domain entrypoint: `tools-server/mcp_banking_server.py`
- Triage domain entrypoint: `tools-server/mcp_triage_server.py`
- Retail, airline, stocks, and banking domains use per-session DB copies (under `tools-server/session_dbs/`)
- Internal error hint logic lives in `tools-server/error_hints.py`

### sandbox-server (port 5051)
- Primary entrypoint: `sandbox-server/mcp_server_codemode.py`
- Exposes `execute_python` and proxies `actions.*` calls to tools-server
- Uses session-aware routing (`mcp-session-id`) and stores run hashes in `sandbox-server/session_hashes/`
- Can start before tools-server and auto-refreshes tool discovery in the background
- Dynamically regenerates and updates `execute_python` description when connected tools change (including data model section)

## Prompts

Domain prompts are stored in:
- `system-prompts/retail-system-prompt.txt`
- `system-prompts/airline-system-prompt.txt`
- `system-prompts/stocks-system-prompt.txt`
- `system-prompts/banking-system-prompt.txt`
- `system-prompts/triage-system-prompt.txt`

Use the prompt that matches the currently running tools server domain.

## Setup

### Prerequisites
- Python 3.10+
- Virtual environment
- Docker + Docker Compose (for containerized run)

### Install dependencies

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

If needed, install server-local requirements too:

```bash
pip install -r tools-server/requirements.txt
pip install -r sandbox-server/requirements.txt
```

Note:
- `sandbox-server` supports two execution engines: `codemode` (default) and `monty`.
- `codemode` requires the `code-mode` Python package (`utcp_code_mode`).
- `monty` requires the `pydantic-monty` package (included in `sandbox-server/requirements.txt`).
- In Docker, this is installed from:
    `https://github.com/universal-tool-calling-protocol/code-mode` (`python-library` subdirectory).

Engine selection:

```bash
python mcp_server_codemode.py --port 5051 --tools-url http://localhost:5050/sse --engine codemode
python mcp_server_codemode.py --port 5051 --tools-url http://localhost:5050/sse --engine monty
```

## Run

### Retail mode

```bash
# Terminal 1
cd tools-server
python mcp_retail_server.py --port 5050

# Terminal 2
cd sandbox-server
python mcp_server_codemode.py --port 5051 --tools-url http://localhost:5050/sse --engine codemode
```

### Airline mode

```bash
# Terminal 1
cd tools-server
python mcp_airline_server.py --port 5050

# Terminal 2
cd sandbox-server
python mcp_server_codemode.py --port 5051 --tools-url http://localhost:5050/sse --engine codemode
```

### Stocks mode

```bash
# Terminal 1
cd tools-server
python mcp_stocks_server.py --port 5050

# Terminal 2
cd sandbox-server
python mcp_server_codemode.py --port 5051 --tools-url http://localhost:5050/sse --engine codemode
```

### Banking mode

```bash
# Terminal 1
cd tools-server
python mcp_banking_server.py --port 5050

# Terminal 2
cd sandbox-server
python mcp_server_codemode.py --port 5051 --tools-url http://localhost:5050/sse --engine codemode
```

### Triage mode

```bash
# Terminal 1
cd tools-server
python mcp_triage_server.py --port 5050

# Terminal 2
cd sandbox-server
python mcp_server_codemode.py --port 5051 --tools-url http://localhost:5050/sse --engine codemode
```

## Run with Docker

From `mcp-agent-servers/`:

```bash
docker compose up --build
```

This starts:
- `tools-server` on `http://localhost:5050/sse`
- `sandbox-server` on `http://localhost:5051/sse`
- `sandbox-server` waits for healthy `tools-server` before startup

By default, `tools-server` runs in **retail** mode.

To run **airline** mode:

```bash
MCP_DOMAIN=airline docker compose up --build
```

To run **stocks** mode:

```bash
MCP_DOMAIN=stocks docker compose up --build
```

To run **banking** mode:

```bash
MCP_DOMAIN=banking docker compose up --build
```

To run **triage** mode:

```bash
MCP_DOMAIN=triage docker compose up --build
```

Notes:
- Compose mounts `./data` into the tools container at `/data`.
- Default DB paths inside container are:
    - retail: `/data/retail/db.json`
    - airline: `/data/airline/db.json`
    - stocks: `/data/stocks/db.json`
    - banking: `/data/banking/db.json`
    - triage: no DB required
- You can override with env vars:
    - `RETAIL_DB_PATH=/custom/path.json`
    - `AIRLINE_DB_PATH=/custom/path.json`
    - `STOCKS_DB_PATH=/custom/path.json`
    - `BANKING_DB_PATH=/custom/path.json`
- Compose sets `NO_PROXY`/`no_proxy` for internal service-to-service calls to avoid proxy-induced `504` errors.

> **Proxy note:** If `docker compose build` fails with `Network is unreachable` during `pip install`, configure Docker build proxy in `~/.docker/config.json`:
>
> ```json
> { "proxies": { "default": { "httpProxy": "http://your-proxy:port", "httpsProxy": "http://your-proxy:port" } } }
> ```
>
> Then re-run `docker compose up --build -d`.

> **Flowise version note:** Flowise `3.1.x` has a breaking change in its MCP SSE client that causes `Invalid response body, expected a web ReadableStream` errors. The EI agenticai plugin pins Flowise to `3.0.12` which works correctly.

Before first run, download the tau2-bench database files for **airline** and **retail** domains (or let the servers auto-download them on first startup):

```bash
curl -L -o ./data/airline/db.json \
  https://raw.githubusercontent.com/sierra-research/tau2-bench/main/data/tau2/domains/airline/db.json

curl -L -o ./data/retail/db.json \
  https://raw.githubusercontent.com/sierra-research/tau2-bench/main/data/tau2/domains/retail/db.json
```

> **Note:** If you are behind a corporate proxy, add `-x http://<proxy>:<port>` to the `curl` commands. Auto-download inside Docker containers respects the system proxy settings.

The **banking** and **stocks** databases are included in the repository (`data/banking/db.json`, `data/stocks/db.json`). The **triage** domain does not require a database.

Useful commands:

```bash
docker compose build --no-cache
docker compose up
# or detached
docker compose up -d
docker compose logs -f sandbox-server tools-server
docker compose down
```

## Flowise MCP Config

When adding the MCP Custom SSE node in Flowise, point it at the sandbox-server. Since Flowise runs inside the K8s cluster (deployed by EI), use the host IP or K8s service to reach the sandbox-server running on Docker:

```json
{
    "url": "http://<host-ip>:5051/sse",
    "transport": "sse"
}
```

> Find your host IP: `hostname -I | awk '{print $1}'`
```

## Flowise Flows & Prompt Field

- Saved/exported Flowise flows for this project are kept in `Flowise/`.
- In Flowise, open the **Tool Agent** node and paste the matching prompt into the **System Prompt** field:
    - Retail runs → `system-prompts/retail-system-prompt.txt`
    - Airline runs → `system-prompts/airline-system-prompt.txt`
    - Stocks runs → `system-prompts/stocks-system-prompt.txt`
    - Banking runs → `system-prompts/banking-system-prompt.txt`
    - Triage runs → `system-prompts/triage-system-prompt.txt`
- Ensure the selected system prompt matches the tools server domain currently running on port `5050`.

---

## Deploy the LLM

You need a running vLLM endpoint serving `Qwen/Qwen3-Coder-30B-A3B-Instruct` (or a compatible tool-calling model). Choose one of the options below.

### Option A: Enterprise Inference (Kubernetes)

Deploy vLLM via the Enterprise Inference Helm charts. `Qwen/Qwen3-Coder-30B-A3B-Instruct` is not in the EI pre-validated model menu, but vLLM supports it natively — deploy it directly with the vLLM Helm chart.

#### Pre-download model (recommended)

```bash
pip install huggingface_hub
huggingface-cli login
huggingface-cli download Qwen/Qwen3-Coder-30B-A3B-Instruct
```

#### TP=1 (recommended for simplicity)

Single worker, OS-managed thread scheduling. Best starting point — avoids NUMA binding complexity.

```bash
cd /path/to/Enterprise-Inference
helm install vllm-qwen3-coder ./core/helm-charts/vllm \
  -n default \
  -f ./core/helm-charts/vllm/xeon-values.yaml \
  --set LLM_MODEL_ID="Qwen/Qwen3-Coder-30B-A3B-Instruct" \
  --set shmSize="4Gi" \
  --set tensor_parallel_size="1" \
  --set pipeline_parallel_size="1" \
  --set-string configMapOverrides.VLLM_CPU_OMP_THREADS_BIND="all" \
  --set-string configMapOverrides.VLLM_CPU_KVCACHE_SPACE="10" \
  --set-string configMapOverrides.VLLM_CPU_NUM_OF_RESERVED_CPU="0"
```

| Parameter | Value | Why |
|---|---|---|
| `tensor_parallel_size` | `1` | Single worker — no multi-process coordination |
| `VLLM_CPU_OMP_THREADS_BIND` | `all` | Skips manual thread binding — avoids NRI/NUMA conflicts |
| `VLLM_CPU_KVCACHE_SPACE` | `10` GB | Sufficient for `max-num-seqs=8` |
| `VLLM_CPU_NUM_OF_RESERVED_CPU` | `0` | Must be 0 — value of 1 causes binding to NRI-reserved core 0 |

#### TP=2 (better throughput, requires NUMA-aware binding)

Splits the model across 2 workers. Each worker must be bound to specific NUMA nodes. You **must** provide explicit `VLLM_CPU_OMP_THREADS_BIND` ranges.

First, find your NUMA topology and NRI reserved cores:

```bash
lscpu | grep -E "NUMA node[0-9]"
kubectl get configmap -n kube-system nri-resource-policy-balloons-config -o yaml | grep -A5 reservedResources
```

Build per-worker bind ranges that **exclude** NRI-reserved cores. Format: `<worker0-cores>|<worker1-cores>`.

Example for a 4-NUMA-node machine where NRI reserves cores 0, 43, 86, 129, 172, 215, 258, 301:

```bash
helm install vllm-qwen3-coder ./core/helm-charts/vllm \
  -n default \
  -f ./core/helm-charts/vllm/xeon-values.yaml \
  --set LLM_MODEL_ID="Qwen/Qwen3-Coder-30B-A3B-Instruct" \
  --set shmSize="4Gi" \
  --set tensor_parallel_size="2" \
  --set pipeline_parallel_size="1" \
  --set-string configMapOverrides.VLLM_CPU_OMP_THREADS_BIND="1-42\,173-214\,87-128\,259-300|44-85\,216-257\,130-171\,302-343" \
  --set-string configMapOverrides.VLLM_CPU_KVCACHE_SPACE="20" \
  --set-string configMapOverrides.VLLM_CPU_NUM_OF_RESERVED_CPU="0"
```

> **Warning:** The bind ranges above are specific to one machine. You **must** adapt them to your NUMA layout and NRI reserved cores. Using incorrect ranges causes `sched_setaffinity errno: 22` crashes.

#### Post-install verification

```bash
# Check pod status (model loading takes ~2-5 min on CPU)
kubectl get pods -n default | grep vllm
kubectl logs -n default -l app.kubernetes.io/instance=vllm-qwen3-coder -f

# Verify model is serving
curl -s --noproxy '*' http://$(kubectl get svc vllm-qwen3-coder-service -n default -o jsonpath='{.spec.clusterIP}')/v1/models
```

Your vLLM endpoint for Flowise:
```
http://vllm-qwen3-coder-service.default.svc.cluster.local/v1
```

> **Note:** The K8s service listens on port **80** (not 8000). Use the URL above without a port number.

#### vLLM v0.16.0: LOGNAME fix

The v0.16.0 image runs as UID 1001 without a `/etc/passwd` entry, causing `getpwuid()` errors. Fix:

```bash
kubectl patch configmap vllm-qwen3-coder-config -n default --type=merge -p='{"data":{"LOGNAME":"vllm"}}'
kubectl rollout restart deployment/vllm-qwen3-coder -n default
```

#### Behind a corporate proxy

If the vLLM pod cannot reach HuggingFace (`Network is unreachable` or `ConnectionError` in logs), set the proxy in the configmap:

```bash
kubectl patch configmap vllm-qwen3-coder-config -n default --type=merge \
  -p='{"data":{"http_proxy":"http://your-proxy:port","https_proxy":"http://your-proxy:port","no_proxy":"localhost,127.0.0.1,.svc,.svc.cluster.local,10.0.0.0/8"}}'
kubectl rollout restart deployment/vllm-qwen3-coder -n default
```

If the model weights are already cached on the PVC and you want to skip any network access, use offline mode instead:

```bash
kubectl patch configmap vllm-qwen3-coder-config -n default --type=merge -p='{"data":{"HF_HUB_OFFLINE":"1"}}'
kubectl rollout restart deployment/vllm-qwen3-coder -n default
```

### Option B: Standalone Docker

Run vLLM directly in Docker on a CPU machine (**~80 GB free RAM** required).

#### Pre-download model (recommended)

```bash
pip install huggingface_hub
huggingface-cli login
huggingface-cli download Qwen/Qwen3-Coder-30B-A3B-Instruct
```

#### Start vLLM container

```bash
export HF_TOKEN="hf_your_token_here"

docker run -d --name vllm-qwen3-coder \
  -p 8000:8000 \
  --ipc=host \
  --security-opt seccomp=unconfined \
  -e HF_TOKEN=${HF_TOKEN} \
  -e VLLM_CPU_KVCACHE_SPACE=10 \
  -e VLLM_CPU_NUM_OF_RESERVED_CPU=0 \
  -e LOGNAME=vllm \
  -v ~/.cache/huggingface:/root/.cache/huggingface \
  public.ecr.aws/q9t5s3a7/vllm-cpu-release-repo:v0.16.0 \
    --model Qwen/Qwen3-Coder-30B-A3B-Instruct \
    --dtype bfloat16 \
    --max-model-len 32768 \
    --max-num-seqs 8 \
    --enable-auto-tool-choice \
    --tool-call-parser qwen3_coder \
    --port 8000
```

| Parameter | Value | Notes |
|---|---|---|
| `--ipc=host` | — | Required for shared memory between vLLM processes |
| `--security-opt seccomp=unconfined` | — | Required for `sched_setaffinity` thread binding |
| `VLLM_CPU_KVCACHE_SPACE` | `10` | 10 GB KV cache — sufficient for `max-num-seqs=8` |
| `VLLM_CPU_NUM_OF_RESERVED_CPU` | `0` | Avoids thread binding to reserved cores |
| `--tool-call-parser` | `qwen3_coder` | Required for Qwen3-Coder tool calling format |
| `LOGNAME` | `vllm` | Fixes `getpwuid()` error in v0.16.0 |

#### Wait and verify

Model loading takes **3-10 minutes** on CPU:

```bash
docker logs -f vllm-qwen3-coder          # watch progress
curl -s http://localhost:8000/v1/models   # should return model name
```

> **Proxy:** If `public.ecr.aws` is blocked, pull from a machine with access and transfer via `docker save`/`docker load`.

---

## Configure Flowise

Flowise is deployed separately via the **Enterprise Inference agenticai plugin**. See [plugins/agenticai/docs/agenticai-quickstart.md](../../plugins/agenticai/docs/agenticai-quickstart.md) for full deployment and setup instructions.

**Quick summary:**

1. Enable in `core/inventory/inference-config.cfg`:
   ```properties
   deploy_agenticai_plugin=on
   ```
2. Deploy: `cd core && bash inference-stack-deploy.sh` → select *Provision Enterprise Inference Cluster*
3. Verify: `kubectl get pods -n flowise`
4. Access: `https://flowise-<your-domain>`

Once Flowise is running, configure it for this sample:

### a. Add credential

1. Left sidebar → **Credentials**
2. **Add Credential** → **OpenAI API**
3. Name: `vLLM-local`
4. API Key: `sk-dummy`
5. Save

> You must enter `sk-dummy` — Flowise requires a non-empty key even though vLLM does not validate it.

### b. Import an AgentFlow

1. Left sidebar → **AgentFlows** → **Add New**
2. Top-right → **Settings** gear → **Load Agents**
3. Import a template from the `Flowise/` directory:
   - `Flowise/agentflow_code_execution_retail.json` — for retail domain
   - `Flowise/agentflow_code_execution_stocks.json` — for stocks domain
   - `Flowise/agentflow_code_execution_triage.json` — for triage domain

### c. Update endpoints

**LLM nodes (ChatOpenAI Compatible):**

| Field | Value |
|---|---|
| Credential | `vLLM-local` |
| Base Path | `http://<vllm-host>:<port>/v1` |
| Model Name | `Qwen/Qwen3-Coder-30B-A3B-Instruct` |
| Temperature | `0` |

Replace `<vllm-host>:<port>` with your vLLM endpoint:

| Deployment | Base Path example |
|---|---|
| Option A (EI) | `http://vllm-qwen3-coder-service.default.svc.cluster.local/v1` (port 80, no port needed) |
| Option A (EI, from outside cluster) | `http://<node-ip>:<nodeport>/v1` |
| Option B (Docker, same host) | `http://<host-ip>:8000/v1` |

> Find your host IP: `hostname -I | awk '{print $1}'`

**MCP node (Custom MCP SSE transport):**

| Field | Value |
|---|---|
| URL | `http://<host-ip>:5051/sse` |

> Use the host IP or a resolvable hostname — Flowise runs in the K8s cluster and needs to reach the sandbox-server on the Docker host.

### d. Set system prompt

In the **Tool Agent** node, paste the contents of the matching system prompt file:

| Domain | Prompt file |
|---|---|
| retail | `system-prompts/retail-system-prompt.txt` |
| airline | `system-prompts/airline-system-prompt.txt` |
| stocks | `system-prompts/stocks-system-prompt.txt` |
| banking | `system-prompts/banking-system-prompt.txt` |
| triage | `system-prompts/triage-system-prompt.txt` |

### e. Save the flow

Click **Save**, give it a name, save.

---

## Stopping

```bash
docker compose down
```

To also remove volumes (session data):
```bash
docker compose down -v
```

To stop vLLM (if using Option B Docker):
```bash
docker stop vllm-qwen3-coder && docker rm vllm-qwen3-coder
```

To remove EI vLLM (if using Option A):
```bash
helm uninstall vllm-qwen3-coder -n default
```

---

## Port Summary

| Service | URL | Purpose |
|---|---|---|
| vLLM (Option A) | `http://vllm-qwen3-coder-service.default.svc.cluster.local/v1` | LLM API (K8s internal, port 80) |
| vLLM (Option B) | `http://localhost:8000/v1` | LLM API (Docker, port 8000) |
| tools-server | `http://localhost:5050/sse` | MCP domain tools (used by sandbox internally) |
| sandbox-server | `http://localhost:5051/sse` | MCP sandbox endpoint (Flowise connects here) |

---

## Configuration

Settings in `.env`:

| Variable | Default | Description |
|---|---|---|
| `MCP_DOMAIN` | `retail` | Domain to run (retail, airline, stocks, banking, triage) |

---

## Troubleshooting

### Docker build fails behind proxy

If `docker compose build` fails with `Network is unreachable` during `pip install`, configure Docker build proxy in `~/.docker/config.json`:

```json
{
  "proxies": {
    "default": {
      "httpProxy": "http://your-proxy:port",
      "httpsProxy": "http://your-proxy:port",
      "noProxy": "localhost,127.0.0.1"
    }
  }
}
```

Then re-run `docker compose up --build -d`. The proxy is only needed at build time — containers themselves use `NO_PROXY` for inter-service communication.

### Flowise: `isDeniedIP: Access to this host is denied by policy`

Flowise has a built-in HTTP deny list that blocks connections to private IP ranges (`10.0.0.0/8`, `172.16.0.0/12`, etc.). When deployed via EI, ensure the `HTTP_SECURITY_CHECK` environment variable is set to `false` in the Flowise deployment. Check:

```bash
kubectl exec -n flowise deploy/flowise -- env | grep HTTP_SECURITY_CHECK
```

### Flowise: `Invalid response body, expected a web ReadableStream`

You are running Flowise `3.1.x` or newer, which broke MCP SSE compatibility. The EI agenticai plugin pins Flowise to `3.0.12`. Verify the running version:

```bash
kubectl get deployment -n flowise flowise -o jsonpath='{.spec.template.spec.containers[0].image}'
```

If it shows a version newer than `3.0.12`, update the image tag in `plugins/agenticai/vars/agenticai-plugin-vars.yml` and redeploy.

### Flowise can't reach vLLM

- Confirm vLLM is healthy: `curl http://<vllm-host>:<port>/health`
- Use the host IP, not `localhost`, in the Flowise LLM node Base Path
- If using EI (Option A), the K8s service is on port **80** — do not append `:8000`
- Since Flowise runs in K8s, use the K8s internal service URL: `http://vllm-qwen3-coder-service.default.svc.cluster.local/v1`

### MCP tools not visible in Flowise

- Verify sandbox-server is running: `docker compose ps`
- Check the MCP endpoint URL in Flowise uses your host IP: `http://<host-ip>:5051/sse`
- Check both MCP container logs: `docker compose logs -f sandbox-server tools-server`

### vLLM OOMKilled (exit code 137)

- Check RAM: `free -h` — need ~80 GB free for the 30B model
- Reduce `VLLM_CPU_KVCACHE_SPACE` to `5` or use a smaller model
- On multi-NUMA machines with TP=1, use `VLLM_CPU_OMP_THREADS_BIND="all"` to bypass NUMA strict binding (which pins all memory to one ~63 GB NUMA node)

### vLLM crashes with `sched_setaffinity errno: 22`

Your `VLLM_CPU_OMP_THREADS_BIND` ranges include CPU cores reserved by NRI Balloon Policy. Check reserved cores and rebuild ranges:

```bash
kubectl get configmap -n kube-system nri-resource-policy-balloons-config -o yaml | grep -A5 reservedResources
```

### vLLM v0.16.0: `getpwuid(): uid not found: 1001`

Add `LOGNAME=vllm` — see the fix under Option A above, or use `-e LOGNAME=vllm` for Docker.

### vLLM image won't pull (ECR blocked)

Pull from a machine with access and transfer: `docker save` / `docker load`.

---

## Data Attribution

The retail and airline databases are sourced from the [τ-bench](https://github.com/sierra-research/tau2-bench) benchmark by Sierra Research, licensed under MIT. They contain synthetic data designed for evaluating tool-calling agents. The airline and retail servers auto-download these files from tau2-bench on first run if not present locally.
