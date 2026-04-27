# Agentic Code Execution — MCP Agent Servers

Two-server MCP architecture for code-execution agents:
- **tools-server** — domain APIs (retail, airline, stocks, banking, triage) in `examples/`
- **sandbox-server** — `execute_python` with `actions.*` proxy

Designed for Flowise / custom MCP clients.

> **Disclaimer:** This is a reference application intended for demonstration and evaluation purposes only. The `execute_python` tool allows the LLM agent to generate and execute Python code in a sandboxed environment. Review and harden the sandbox security configuration before any production use.

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

## Minimum Hardware Requirements

Measured on a bare-metal deployment with `Qwen/Qwen3-Coder-30B-A3B-Instruct` (BF16, ~57 GB model weights).

| Resource | Minimum | Recommended | Notes |
|---|---|---|---|
| **RAM** | 80 GB | 128 GB | vLLM alone uses ~81 GB RSS (model weights + KV cache + runtime). K8s + Flowise + MCP add ~8 GB. |
| **CPU cores** | 16 | 32+ | vLLM CPU inference is compute-bound. More cores reduce latency. |
| **Disk** | 120 GB | 200 GB | ~57 GB model weights, ~2 GB container images, ~30 GB K8s/containerd, OS overhead. |
| **NUMA** | — | interleave | Multi-socket systems **must** use `numactl --interleave=all` for vLLM. See [NUMA notes](#numa-considerations) below. |

### NUMA considerations

On multi-NUMA-node systems (e.g. dual-socket Xeon), vLLM's IPEX backend migrates all memory to a single NUMA node by default. Since each node typically has only 30–32 GB, the model loading fails with OOM on a 60 GB+ model.

**Solution:** Launch vLLM with memory interleaving and disable IPEX's thread binding:

```bash
VLLM_CPU_OMP_THREADS_BIND=nobind numactl --interleave=all vllm serve <model> ...
```

- `VLLM_CPU_OMP_THREADS_BIND=nobind` — prevents IPEX from calling `numa_migrate_pages()`.
- `numactl --interleave=all` — distributes allocations evenly across all NUMA nodes.

---

## Quick Start (Docker)

```bash
docker compose up --build
```

This starts the **retail** domain by default:
- tools-server on `http://localhost:5050/sse`
- sandbox-server on `http://localhost:5051/sse`

> Other domains are also available (airline, stocks, banking, triage):
> ```bash
> MCP_DOMAIN=airline docker compose up --build
> ```
> You can also set `MCP_DOMAIN` in `.env`.

### Database files

Before first run, download the τ-bench databases for **retail** and **airline** (or let the servers auto-download on first startup):

```bash
curl -L -o ./examples/retail/data/db.json \
  https://raw.githubusercontent.com/sierra-research/tau2-bench/main/data/tau2/domains/retail/db.json

curl -L -o ./examples/airline/data/db.json \
  https://raw.githubusercontent.com/sierra-research/tau2-bench/main/data/tau2/domains/airline/db.json
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

### Enterprise Inference (Kubernetes)

Deploy the model using [Enterprise Inference](../../docs/README.md). EI handles model download, proxy configuration, and basic CPU pinning.

```bash
cd /path/to/Enterprise-Inference
helm install vllm-qwen3-coder ./core/helm-charts/vllm \
  -n default \
  -f ./core/helm-charts/vllm/xeon-values.yaml \
  --set LLM_MODEL_ID="Qwen/Qwen3-Coder-30B-A3B-Instruct"
```

> **Multi-NUMA systems:** If the model is larger than a single NUMA node's memory (e.g. ~60 GB model on a system with 4 × 32 GB NUMA nodes), the default vLLM/IPEX configuration will fail with OOM. You **must** set two environment variables in the vLLM container:
>
> ```
> VLLM_CPU_OMP_THREADS_BIND=nobind
> ```
>
> and launch the process with `numactl --interleave=all`. See [NUMA considerations](#numa-considerations) for details.

See the [EI deployment guide](../../docs/README.md) for full instructions, proxy setup, and troubleshooting.

---

## Configure Flowise

Flowise is deployed separately via the **Enterprise Inference agenticai plugin**. See [plugins/agenticai/docs/agenticai-quickstart.md](../../plugins/agenticai/docs/agenticai-quickstart.md) for deployment instructions.

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
| EI (in-cluster) | `http://vllm-qwen3-coder-service.default.svc.cluster.local/v1` |
| EI (external) | `http://<node-ip>:<nodeport>/v1` |

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

## Example Conversation (Retail)

Below is a sample exchange with the retail agent. This is just one example use case — once the workload is set up, you can have your own conversations and explore the full range of agent capabilities.

> **User:** Hi, I have a couple of questions. First, can you tell me exactly how many t-shirt options are available in your online store right now? Also, I have some pending t-shirt orders and I'd like to change all of them to purple, size small, v-neck, and preferably polyester.
>
> **User:** Sure, my name is Yusuf Rossi and my zip code is 19122.
>
> **User:** I actually don't remember the orders, can you look them up for me?
>
> **User:** Yes, please modify both of these orders
>
> **User:** I confirm
>
> **User:** Now retrieve all my orders and list them with their details

### Try it yourself

The retail database contains 500 synthetic users. Here are two more you can use to start a conversation:

| Authentication method | Value |
|---|---|
| Email | `mia.garcia2723@example.com` |
| Name + Zip | Aarav Anderson, 19031 |

Try asking the agent about their orders, requesting a return on a delivered item, or cancelling a pending order.

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
helm uninstall vllm-qwen3-coder -n default
```

---

## Port Summary

| Service | URL | Notes |
|---|---|---|
| vLLM (EI) | `http://vllm-qwen3-coder-service.default.svc.cluster.local/v1` | K8s internal, port 80 |
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



---

## Data Attribution

The retail and airline databases are sourced from [τ-bench](https://github.com/sierra-research/tau2-bench) by Sierra Research (MIT license). They contain **synthetic data** generated for testing and demonstration purposes only — no personal or real-world data is used. The banking and stocks databases bundled in this repository are also entirely synthetic. The retail and airline databases are auto-downloaded from τ-bench on first run if not present locally.

See [THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES) for full attribution.
