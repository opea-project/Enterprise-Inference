# Enterprise Inference — Airgapped Deployment Demo
**Date**: April 24, 2026  
**Platform**: Intel Xeon (CPU-only) | 2-VM setup

---

## What We're Demonstrating

A fully airgapped deployment of Intel Enterprise Inference (EI) — Kubernetes cluster + LLM serving + GenAI Gateway — with **zero internet access on the deployment machine**.

All packages, images, and binaries are served from a local JFrog Artifactory instance.

---

## Architecture

```
┌──────────────────────────────┐        ┌──────────────────────────────────┐
│  VM1 — JFrog Artifactory     │        │  VM2 — EI Deployment (Airgapped) │
│  100.67.152.208              │◄──LAN──│  100.67.153.209                  │
│                              │        │                                  │
│  Port 8082                   │        │  Internet: BLOCKED (iptables)    │
│  All packages mirrored here  │        │  JFrog: REACHABLE                │
└──────────────────────────────┘        └──────────────────────────────────┘
```

**Key principle**: VM2 has no internet. Every package, image, binary, and model is served from VM1's JFrog.

---

## Step 1 — Package Identification

Everything EI needs was identified across 7 categories:

| Category | Count | JFrog Repo |
|---|---|---|
| Docker images | 40+ | `ei-docker-virtual` (aggregates 6 remotes) |
| Helm charts | 10 | `ei-helm-local` → `ei-helm-virtual` |
| Python packages | 30+ wheels | `ei-pypi-local` → `ei-pypi-virtual` |
| Ansible collections | 4 | `ei-generic-binaries/ansible-collections/` |
| Kubernetes binaries | 9 | `ei-generic-binaries/` (kubectl, helm, runc, containerd, etc.) |
| apt .deb packages | 10+ | `ei-generic-binaries/apt-debs/` |
| LLM model weights | ~4 GB | `ei-generic-models/` |

### Docker Images — Registries Covered
| Source Registry | JFrog Remote Repo |
|---|---|
| `docker.io` | `ei-docker-dockerhub` |
| `ghcr.io` | `ei-docker-ghcr` |
| `public.ecr.aws` | `ei-docker-ecr` |
| `registry.k8s.io` | `ei-docker-k8s` |
| `quay.io` | `ei-docker-quay` |

### Key Images
- vLLM CPU (`public.ecr.aws`) — LLM inference engine
- LiteLLM, Langfuse (`ghcr.io`) — GenAI Gateway + observability
- ingress-nginx, kube-* (`registry.k8s.io`) — Kubernetes control plane
- Calico (`quay.io`) — CNI networking
- Bitnami postgresql, redis, minio (`docker.io`) — GenAI Gateway dependencies

---

## Step 2 — JFrog Setup (Automated)

Single script runs on VM1 (internet-connected):

```bash
./jfrog-setup.sh \
  --jfrog-url http://localhost:8082/artifactory \
  --jfrog-user admin \
  --jfrog-pass password \
  --hf-token <HF_TOKEN> \
  --dockerhub-user <USER> \
  --dockerhub-pass <PAT>
```

### What the script does (10 steps):

| Step | What |
|---|---|
| 1 | Create all JFrog repos (local, remote, virtual) for Docker/Helm/PyPI/Generic |
| 2 | Set anonymous read permissions on all Docker repos |
| 3a | Pull all Docker images from upstream → cache in JFrog via `skopeo` |
| 3b | Upload Helm chart tarballs + generate `index.yaml` |
| 3c | Upload Python wheels to `ei-pypi-local` |
| 3d | Upload `pip.whl` bootstrap wheel |
| 3e | Upload Ansible collection tarballs |
| 3f | Upload apt `.deb` files (jq, libonig5, libjq1 + Kubespray prereqs) |
| 3g | Upload Kubernetes/Kubespray binaries with original URL path structure |
| 3h | Upload Kubespray source tarball |
| 3i/3j | Download + upload LLM model weights (Llama 3.1 8B / Llama 3.2 3B) |

> **One manual step required**: JFrog UI → Administration → Security → General → **Allow Anonymous Access → ON**  
> This cannot be automated via REST API (requires internal `jfac@...` Bearer token).

---

## Step 3 — EI Code Changes for Airgap

EI required code changes to support airgap mode. All changes follow a **dual-task pattern** — original internet task preserved, new JFrog task added with `when: airgap_enabled`.

### Config entry points
```ini
# inference-config.cfg
airgap_enabled=on
jfrog_url=http://100.67.152.208:8082/artifactory
jfrog_username=admin
jfrog_password=password
```

### Key changes made

**Shell scripts** — airgap vars passed as `--extra-vars` to all ansible-playbook calls:
- `ingress-controller.sh`, `genai-gateway-controller.sh`, `keycloak-controller.sh`, `install-model.sh`, `ballon-policy.sh`, `label-nodes.sh`

**Playbooks** — dual Helm repo registration tasks:
- `deploy-ingress-controller.yml`, `deploy-genai-gateway.yml`, `deploy-keycloak-*.yml`

**`setup-env.sh`** — airgap-aware bootstrapping:
- pip from JFrog PyPI mirror (not pypi.org)
- Kubespray from JFrog tarball (not git clone)
- Ansible collections from JFrog (not galaxy.ansible.com)
- apt sources rewritten to point to JFrog Debian mirror
- venv created with `--without-pip`, bootstrapped from JFrog pip wheel

**`prereq-check.sh`** — connectivity check hits JFrog ping endpoint instead of google.com

**`offline.yml`** (Kubespray) — all binary download URLs point to JFrog `ei-generic-binaries`

**`inference-tools` role** — helm install, pip install, jq install all have JFrog paths

**containerd mirrors** — all 5 registries mirrored through JFrog in `all.yml`

---

## Step 4 — Deployment on VM2

```bash
# Internet is blocked
sudo iptables -A OUTPUT ... -j DROP

# Single command — identical to non-airgap deployment
cd ~/Enterprise-Inference/core
./inference-stack-deploy.sh
```

Deploys in order:
1. **Kubernetes** (Kubespray) — all binaries + images from JFrog
2. **Ingress NGINX** — chart from JFrog `ei-helm-virtual`
3. **Keycloak + APISIX** — charts from JFrog, OCI subcharts via JFrog
4. **GenAI Gateway** (LiteLLM + Langfuse) — charts + images from JFrog
5. **vLLM model** — loads weights from local PV (`HF_HUB_OFFLINE=1`)

---

## Validation

### Internet is blocked
```bash
curl -s --max-time 5 https://google.com && echo "OPEN" || echo "BLOCKED"
# BLOCKED ✅
```

### JFrog is reachable
```bash
curl -s http://100.67.152.208:8082/artifactory/api/system/ping
# OK ✅
```

### LLM endpoint responding
```bash
TOKEN=$(curl -s -X POST https://<EI_IP>/realms/master/protocol/openid-connect/token \
  -d "client_id=<client>&client_secret=<secret>&grant_type=client_credentials" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

curl -k -X POST "https://api.example.com/Llama-3.2-3B-Instruct-vllmcpu/v1/completions" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"model":"meta-llama/Llama-3.2-3B-Instruct","prompt":"What is Deep Learning?","max_tokens":25}'
# Returns valid completion ✅
```

### All pods running
```bash
kubectl get pods -A | grep -v Running | grep -v Completed
# No output ✅
```

---

## Key Technical Challenges Solved

| Challenge | Root Cause | Fix |
|---|---|---|
| `docker pull` broken through HTTP JFrog | Docker 29.x forces HTTPS even with `insecure-registries` | Switched to `skopeo` which respects HTTP |
| containerd `skip_verify` breaks HTTP mirrors | Any `skip_verify` field triggers HTTPS-first | Kubespray `hosts.toml.j2` patched to only write it when `true` |
| Manifest cached but blobs not | Fetching manifest via HTTP doesn't pull blobs | `precache_via_remote` now does `skopeo copy` to force blob caching |
| Helm OCI subcharts bypass mirrors | `helm dependency update` uses its own HTTP client, ignores containerd config | Airgap path: pull charts via `helm pull oci://` from JFrog, then `helm dependency build` |
| APISIX subchart URL hardcoded in Chart.yaml | `helm dependency build` resolves repo by URL, not by registered name | Patch `Chart.yaml` repo URL to JFrog before `dependency build` |
| Keycloak OCI chart_ref bypasses mirrors | `oci://registry-1.docker.io/bitnamicharts/keycloak` uses helm OCI client | Switch to `ei-helm/keycloak` (HTTP Helm repo) in airgap mode |
| Kubespray binary downloads | All bin URLs hardcoded to github.com/dl.k8s.io | `offline.yml` redirects all URLs to JFrog `ei-generic-binaries` |
| apt blocked (Kubespray prereqs) | No Debian mirror in JFrog | Created `ei-debian-ubuntu` remote repo; `setup-env.sh` rewrites `sources.list` |
| vLLM stuck at 0/1 in airgap | Missing `HF_HUB_OFFLINE=1` — HuggingFace Hub network validation hangs | Added `{% if airgap_enabled %}` guard in `deploy-inference-models.yml` |
| `busybox:1.28` manifest unknown | Very old tag dropped from Docker Hub v2 API | Pull latest, retag as `1.28`, push to `ei-docker-local` |
| JFrog anonymous access | REST API requires internal `jfac@...` token | UI toggle only — documented as required manual step |
| NRI balloon `self.no_proxy` crash | kubernetes SDK ≥34.x codegen bug | Python fix script deployed by `inference-tools` role |

---

## What's Deployed (Final State)

```
NAMESPACE       NAME                          READY   STATUS
ingress-nginx   ingress-nginx-controller      1/1     Running
genai-gateway   genai-gateway-*               1/1     Running
genai-gateway   genai-gateway-trace-*         1/1     Running
auth-apisix     apisix-*                      1/1     Running
auth-apisix     keycloak-*                    1/1     Running
default         vllm-llama-3-2-3b-cpu         1/1     Running
default         vllm-llama-8b-cpu             1/1     Running
```

**Internet access**: BLOCKED on VM2  
**LLM endpoint**: Responding ✅  
**Source of all packages**: JFrog on VM1 (LAN only) ✅
