# Agentic Code Execution — MCP Agent Servers

Two-server MCP architecture for code-execution agents:
- **tools-server** — domain APIs (retail, airline, stocks, banking, triage) in `examples/`
- **sandbox-server** — `execute_python` with `actions.*` proxy

Designed for Flowise / custom MCP clients.

## Architecture

```
Flowise (or other MCP client)
        └── Custom MCP → sandbox-server (port 5051)
                                                 │ execute_python
                                                 │
                                                 └── MCP client → tools-server (port 5050)
                                                                                             └── retail | airline | stocks | banking | triage
```

**tools-server (port 5050)** — Runs one domain at a time. Retail, airline, stocks, and banking domains use per-session DB copies (under `examples/session_dbs/`). Internal error hint logic in `examples/error_hints.py`.

**sandbox-server (port 5051)** — Exposes `execute_python` and proxies `actions.*` calls to tools-server. Uses session-aware routing (`mcp-session-id`) and stores run hashes in `sandbox-server/session_hashes/`. Starts independently and auto-refreshes tool discovery in the background. Dynamically regenerates `execute_python` description when connected tools change.

## Quick Start (Docker)

```bash
docker compose up --build
```

This starts tools-server on `http://localhost:5050/sse` and sandbox-server on `http://localhost:5051/sse`. Default domain is **retail**.

To switch domains:

```bash
MCP_DOMAIN=airline docker compose up --build    # or stocks, banking, triage
```

You can also set `MCP_DOMAIN` in `.env`.

### Database files

Before first run, download the τ-bench databases for **airline** and **retail** (or let the servers auto-download on first startup):

```bash
curl -L -o ./examples/airline/data/db.json \
  https://raw.githubusercontent.com/sierra-research/tau2-bench/main/data/tau2/domains/airline/db.json

curl -L -o ./examples/retail/data/db.json \
  https://raw.githubusercontent.com/sierra-research/tau2-bench/main/data/tau2/domains/retail/db.json
```

> Behind a corporate proxy? Add `-x http://<proxy>:<port>` to the `curl` commands.

The **banking** and **stocks** databases are included in the repository. The **triage** domain does not use a database.

### Docker notes

- Compose builds the tools-server image from `examples/Dockerfile`.
- Default DB paths are resolved relative to each domain's directory (e.g. `examples/retail/data/db.json`). Override with `RETAIL_DB_PATH`, `AIRLINE_DB_PATH`, `STOCKS_DB_PATH`, `BANKING_DB_PATH`.
- `NO_PROXY`/`no_proxy` is set for internal service-to-service calls.
- If `docker compose build` fails behind a proxy, see [Troubleshooting](#docker-build-fails-behind-proxy).

### Useful commands

```bash
docker compose build --no-cache       # rebuild images
docker compose up -d                   # start detached
docker compose logs -f                 # follow logs
docker compose down                    # stop
docker compose down -v                 # stop + remove session volumes
```

---

## Deploy the LLM

You need a running vLLM endpoint serving `Qwen/Qwen3-Coder-30B-A3B-Instruct` (or a compatible tool-calling model).

### Pre-download model (recommended)

```bash
pip install huggingface_hub
huggingface-cli login
huggingface-cli download Qwen/Qwen3-Coder-30B-A3B-Instruct
```

### Option A: Enterprise Inference (Kubernetes)

Deploy vLLM via the EI Helm charts. `Qwen/Qwen3-Coder-30B-A3B-Instruct` is not in the EI pre-validated model menu, but vLLM supports it natively.

#### TP=1 (recommended for simplicity)

Single worker, OS-managed scheduling. Best starting point — avoids NUMA binding complexity.

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
| `VLLM_CPU_OMP_THREADS_BIND` | `all` | Skips manual binding — avoids NRI/NUMA conflicts |
| `VLLM_CPU_KVCACHE_SPACE` | `10` GB | Sufficient for `max-num-seqs=8` |
| `VLLM_CPU_NUM_OF_RESERVED_CPU` | `0` | Must be 0 — value of 1 causes binding to NRI-reserved core 0 |

#### TP=2 (better throughput, requires NUMA-aware binding)

Splits the model across 2 workers, each bound to specific NUMA nodes. You **must** provide explicit `VLLM_CPU_OMP_THREADS_BIND` ranges.

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

> **Warning:** The bind ranges above are machine-specific. Adapt them to your NUMA layout and NRI reserved cores. Incorrect ranges cause `sched_setaffinity errno: 22` crashes.

#### Post-install verification

```bash
kubectl get pods -n default | grep vllm
kubectl logs -n default -l app.kubernetes.io/instance=vllm-qwen3-coder -f

curl -s --noproxy '*' http://$(kubectl get svc vllm-qwen3-coder-service -n default -o jsonpath='{.spec.clusterIP}')/v1/models
```

Your vLLM endpoint for Flowise:
```
http://vllm-qwen3-coder-service.default.svc.cluster.local/v1
```

> The K8s service listens on port **80** (not 8000). Use the URL above without a port number.

#### vLLM v0.16.0: LOGNAME fix

The v0.16.0 image runs as UID 1001 without a `/etc/passwd` entry, causing `getpwuid()` errors. Fix:

```bash
kubectl patch configmap vllm-qwen3-coder-config -n default --type=merge -p='{"data":{"LOGNAME":"vllm"}}'
kubectl rollout restart deployment/vllm-qwen3-coder -n default
```

#### Behind a corporate proxy

If the vLLM pod can't reach HuggingFace, set the proxy:

```bash
kubectl patch configmap vllm-qwen3-coder-config -n default --type=merge \
  -p='{"data":{"http_proxy":"http://your-proxy:port","https_proxy":"http://your-proxy:port","no_proxy":"localhost,127.0.0.1,.svc,.svc.cluster.local,10.0.0.0/8"}}'
kubectl rollout restart deployment/vllm-qwen3-coder -n default
```

If the model weights are already cached and you want to skip network access:

```bash
kubectl patch configmap vllm-qwen3-coder-config -n default --type=merge -p='{"data":{"HF_HUB_OFFLINE":"1"}}'
kubectl rollout restart deployment/vllm-qwen3-coder -n default
```

### Option B: Standalone Docker

Run vLLM in Docker on a CPU machine (**~80 GB free RAM** required).

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
| `--ipc=host` | — | Required for shared memory |
| `--security-opt seccomp=unconfined` | — | Required for `sched_setaffinity` |
| `VLLM_CPU_KVCACHE_SPACE` | `10` | 10 GB KV cache |
| `VLLM_CPU_NUM_OF_RESERVED_CPU` | `0` | Avoids binding to reserved cores |
| `--tool-call-parser` | `qwen3_coder` | Required for Qwen3 tool calling |
| `LOGNAME` | `vllm` | Fixes `getpwuid()` in v0.16.0 |

Model loading takes **3-10 minutes** on CPU:

```bash
docker logs -f vllm-qwen3-coder
curl -s http://localhost:8000/v1/models
```

> If `public.ecr.aws` is blocked, pull from a machine with access and transfer via `docker save`/`docker load`.

---

## Configure Flowise

Flowise is deployed separately via the **Enterprise Inference agenticai plugin**. See [plugins/agenticai/docs/agenticai-quickstart.md](../../plugins/agenticai/docs/agenticai-quickstart.md) for deployment instructions.

**Quick summary:**

1. Enable in `core/inventory/inference-config.cfg`:
   ```properties
   deploy_agenticai_plugin=on
   ```
2. Deploy: `cd core && bash inference-stack-deploy.sh` → select *Provision Enterprise Inference Cluster*
3. Verify: `kubectl get pods -n flowise`
4. Access: `https://flowise-<your-domain>`

Once Flowise is running:

### a. Add credential

1. **Credentials** → **Add Credential** → **OpenAI API**
2. Name: `vLLM-local`, API Key: `sk-dummy` → Save

> Flowise requires a non-empty key even though vLLM does not validate it.

### b. Import an AgentFlow

1. **AgentFlows** → **Add New** → top-right **Settings** gear → **Load Agents**
2. Import from `Flowise/`:
   - `agentflow_code_execution_retail.json`
   - `agentflow_code_execution_stocks.json`
   - `agentflow_code_execution_triage.json`

### c. Update endpoints

**LLM nodes (ChatOpenAI Compatible):**

| Field | Value |
|---|---|
| Credential | `vLLM-local` |
| Base Path | `http://<vllm-host>:<port>/v1` |
| Model Name | `Qwen/Qwen3-Coder-30B-A3B-Instruct` |
| Temperature | `0` |

| Deployment | Base Path |
|---|---|
| Option A (EI, in-cluster) | `http://vllm-qwen3-coder-service.default.svc.cluster.local/v1` |
| Option A (EI, external) | `http://<node-ip>:<nodeport>/v1` |
| Option B (Docker) | `http://<host-ip>:8000/v1` |

> Find your host IP: `hostname -I | awk '{print $1}'`

**MCP node (Custom MCP SSE):**

| Field | Value |
|---|---|
| URL | `http://<host-ip>:5051/sse` |

> Flowise runs in K8s — use the host IP, not `localhost`.

### d. Set system prompt

In the **Tool Agent** node, paste the contents of the matching system prompt (see [Domains](#domains) table).

### e. Save and test

Click **Save**, give it a name, and start chatting.

---

## Development (without Docker)

For local development, install dependencies and run servers manually.

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
pip install -r examples/requirements.txt
pip install -r sandbox-server/requirements.txt
```

Run any domain (two terminals):

```bash
# Terminal 1 — tools server (pick one domain)
cd examples/retail
python mcp_retail_server.py --port 5050       # or cd ../airline && python mcp_airline_server.py, etc.

# Terminal 2 — sandbox server (same for all domains)
cd sandbox-server
python mcp_server_codemode.py --port 5051 --tools-url http://localhost:5050/sse --engine codemode
```

Engine options: `codemode` (default, requires `utcp_code_mode`) or `monty` (requires `pydantic-monty`).

---

## Stopping

```bash
docker compose down            # stop MCP servers
docker compose down -v         # + remove session volumes
```

vLLM cleanup:

```bash
# Option A (EI)
helm uninstall vllm-qwen3-coder -n default

# Option B (Docker)
docker stop vllm-qwen3-coder && docker rm vllm-qwen3-coder
```

---

## Port Summary

| Service | URL | Notes |
|---|---|---|
| vLLM (Option A) | `http://vllm-qwen3-coder-service.default.svc.cluster.local/v1` | K8s internal, port 80 |
| vLLM (Option B) | `http://localhost:8000/v1` | Docker, port 8000 |
| tools-server | `http://localhost:5050/sse` | Internal — used by sandbox |
| sandbox-server | `http://localhost:5051/sse` | Flowise connects here |

---

## Configuration

Settings in `.env`:

| Variable | Default | Description |
|---|---|---|
| `MCP_DOMAIN` | `retail` | Domain to run (retail, airline, stocks, banking, triage) |

---

## Troubleshooting

### Docker build fails behind proxy

Configure Docker build proxy in `~/.docker/config.json`:

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

Then re-run `docker compose up --build`. The proxy is only needed at build time.

### Flowise: `isDeniedIP: Access to this host is denied by policy`

Flowise blocks connections to private IPs by default. Ensure `HTTP_SECURITY_CHECK=false` in the Flowise deployment:

```bash
kubectl exec -n flowise deploy/flowise -- env | grep HTTP_SECURITY_CHECK
```

### Flowise: `Invalid response body, expected a web ReadableStream`

Flowise `3.1.x` broke MCP SSE compatibility. The EI plugin pins to `3.0.12`. Verify:

```bash
kubectl get deployment -n flowise flowise -o jsonpath='{.spec.template.spec.containers[0].image}'
```

If it shows a version newer than `3.0.12`, update the image tag in `plugins/agenticai/vars/agenticai-plugin-vars.yml` and redeploy.

### Flowise can't reach vLLM

- Confirm vLLM is healthy: `curl http://<vllm-host>:<port>/health`
- Use host IP, not `localhost`, in the LLM Base Path
- EI service is port **80** — don't append `:8000`
- K8s internal URL: `http://vllm-qwen3-coder-service.default.svc.cluster.local/v1`

### MCP tools not visible in Flowise

- Check sandbox is running: `docker compose ps`
- URL must use host IP: `http://<host-ip>:5051/sse`
- Check logs: `docker compose logs -f sandbox-server tools-server`

### vLLM OOMKilled (exit code 137)

- Need ~80 GB free RAM (`free -h`)
- Reduce `VLLM_CPU_KVCACHE_SPACE` to `5` or use a smaller model
- With TP=1, use `VLLM_CPU_OMP_THREADS_BIND="all"` to avoid NUMA strict binding

### vLLM: `sched_setaffinity errno: 22`

`VLLM_CPU_OMP_THREADS_BIND` includes NRI-reserved cores. Check and rebuild ranges:

```bash
kubectl get configmap -n kube-system nri-resource-policy-balloons-config -o yaml | grep -A5 reservedResources
```

### vLLM v0.16.0: `getpwuid(): uid not found: 1001`

Add `LOGNAME=vllm` — see [LOGNAME fix](#vllm-v0160-logname-fix) above, or `-e LOGNAME=vllm` for Docker.

### vLLM image won't pull (ECR blocked)

Pull from a machine with access and transfer: `docker save` / `docker load`.

---

## Data Attribution

The retail and airline databases are sourced from [τ-bench](https://github.com/sierra-research/tau2-bench) by Sierra Research (MIT license). They contain synthetic data for evaluating tool-calling agents. The servers auto-download these files on first run if not present locally.
