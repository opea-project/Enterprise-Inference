# Airgapped Deployment Guide

This guide covers end-to-end deployment of Enterprise Inference (EI) in an airgapped environment using JFrog Artifactory as a local mirror on a separate internet-connected VM.

## Architecture

```
VM1 (internet-connected)          VM2 (airgapped)
┌─────────────────────┐           ┌─────────────────────┐
│  JFrog Artifactory  │◄──LAN────►│  EI Deployment      │
│  :8082              │           │  Kubernetes + vLLM  │
│  - Docker images    │           │                     │
│  - Helm charts      │           │  No internet access │
│  - PyPI packages    │           │  All pulls → JFrog  │
│  - Binaries         │           └─────────────────────┘
│  - LLM models       │
└─────────────────────┘
```

---

## Step 1 — Install JFrog Artifactory on VM1 (internet-connected)

VM1 must have internet access and be reachable from VM2 over LAN.

### Install via Docker

```bash
# Pull and run JFrog Artifactory OSS
docker run -d \
  --name artifactory \
  -p 8082:8082 \
  -p 8081:8081 \
  -v artifactory-data:/var/opt/jfrog/artifactory \
  releases-docker.jfrog.io/jfrog/artifactory-oss:latest
```

Access the UI at `http://<VM1-IP>:8082`. Default credentials: `admin` / `password`.

**Enable anonymous read access** (required so VM2 can pull without credentials for Docker mirrors):
- Admin → Security → Settings → Enable "Allow Anonymous Access"
- Set Read permission on `ei-docker` and `ei-docker-virtual` for anonymous users

---

## Step 2 — Create Repositories in JFrog

Create the following repositories via Admin → Repositories → Add Repository:

### Docker Repositories

| Name | Type | Remote URL | Notes |
|---|---|---|---|
| `ei-docker` | Local | — | Manually pushed images |
| `ei-docker-dockerhub` | Remote | `https://registry-1.docker.io` | Bitnami, Langfuse, etcd |
| `ei-docker-ecr` | Remote | `https://public.ecr.aws` | vLLM CPU image |
| `ei-docker-ghcr` | Remote | `https://ghcr.io` | TGI, TEI, LiteLLM, NRI plugins |
| `ei-docker-k8s` | Remote | `https://registry.k8s.io` | Kubernetes components |
| `ei-docker-quay` | Remote | `https://quay.io` | Calico |
| `ei-docker-virtual` | Virtual | — | Aggregates all above |

For the virtual repo, add all remote and local repos as members.

### Helm Repository

| Name | Type | Notes |
|---|---|---|
| `ei-helm-local` | Local (Generic) | Charts uploaded as HTTP tarballs |
| `ei-helm-virtual` | Virtual | Aggregates `ei-helm-local` |

> **Important**: Create `ei-helm-local` as **Generic** type (not Helm/HelmOCI). Charts are uploaded via HTTP REST and `index.yaml` is manually generated.

### PyPI Repository

| Name | Type | Remote URL |
|---|---|---|
| `ei-pypi-local` | Local | — |
| `ei-pypi-remote` | Remote | `https://pypi.org` |
| `ei-pypi-virtual` | Virtual | Aggregates both |

### Generic Repository

| Name | Type | Contents |
|---|---|---|
| `ei-generic-binaries` | Local | kubectl, helm, yq, kubespray, ansible collections, Kubernetes binaries |
| `ei-generic-models` | Local | LLM model files (~30 GB) |

---

## Step 3 — Pre-load All Required Assets into JFrog

All commands below run on **VM1** (internet access).

### 3a — Docker Images (cache via JFrog remote repos)

Pull each image through JFrog so it gets cached in the remote repo:

```bash
JFROG=100.67.152.212:8082

# vLLM CPU
docker pull $JFROG/ei-docker-virtual/q9t5s3a7/vllm-cpu-release-repo:v0.10.2

# GenAI Gateway (TGI, TEI, LiteLLM) — needed if deploy_genai_gateway=on
docker pull $JFROG/ei-docker-virtual/ghcr.io/huggingface/text-generation-inference:2.4.0-intel-cpu
docker pull $JFROG/ei-docker-virtual/ghcr.io/huggingface/text-embeddings-inference:cpu-1.7
docker pull $JFROG/ei-docker-virtual/ghcr.io/berriai/litellm-non_root:main-v1.75.8-stable

# Langfuse (observability) — needed if deploy_observability=on
docker pull $JFROG/ei-docker-virtual/langfuse/langfuse:3.106.1
docker pull $JFROG/ei-docker-virtual/langfuse/langfuse-worker:3.106.1

# Keycloak + PostgreSQL
docker pull $JFROG/ei-docker-virtual/bitnamilegacy/keycloak:25.0.2-debian-12-r2
docker pull $JFROG/ei-docker-virtual/bitnamilegacy/postgresql:16.3.0-debian-12-r23
docker pull $JFROG/ei-docker-virtual/bitnamilegacy/postgresql:17.5.0-debian-12-r0

# Redis, MinIO, ClickHouse, Valkey, Zookeeper (GenAI Gateway + observability)
docker pull $JFROG/ei-docker-virtual/bitnamilegacy/redis:8.0.1-debian-12-r0
docker pull $JFROG/ei-docker-virtual/bitnami/minio:2024.12.18
docker pull $JFROG/ei-docker-virtual/bitnami/mc:2024.12.18
docker pull $JFROG/ei-docker-virtual/bitnamilegacy/clickhouse:25.2.1-debian-12-r0
docker pull $JFROG/ei-docker-virtual/bitnamilegacy/valkey:8.0.2-debian-12-r2
docker pull $JFROG/ei-docker-virtual/bitnamilegacy/zookeeper:3.9.3-debian-12-r8
docker pull $JFROG/ei-docker-virtual/bitnamilegacy/os-shell:12-debian-12-r48

# APISIX
docker pull $JFROG/ei-docker-virtual/apache/apisix:3.9.1-debian

# Ingress-nginx
docker pull $JFROG/ei-docker-virtual/ingress-nginx/controller:v1.12.2
docker pull $JFROG/ei-docker-virtual/ingress-nginx/kube-webhook-certgen:v1.5.3

# Kubernetes components
docker pull $JFROG/ei-docker-virtual/pause:3.10
docker pull $JFROG/ei-docker-virtual/kube-apiserver:v1.30.4
docker pull $JFROG/ei-docker-virtual/kube-controller-manager:v1.30.4
docker pull $JFROG/ei-docker-virtual/kube-scheduler:v1.30.4
docker pull $JFROG/ei-docker-virtual/kube-proxy:v1.30.4
docker pull $JFROG/ei-docker-virtual/coredns/coredns:v1.11.1
docker pull $JFROG/ei-docker-virtual/dns/k8s-dns-node-cache:1.22.28
docker pull $JFROG/ei-docker-virtual/cpa/cluster-proportional-autoscaler:v1.8.8

# Calico
docker pull $JFROG/ei-docker-virtual/calico/node:v3.28.1
docker pull $JFROG/ei-docker-virtual/calico/cni:v3.28.1
docker pull $JFROG/ei-docker-virtual/calico/kube-controllers:v3.28.1
docker pull $JFROG/ei-docker-virtual/calico/pod2daemon-flexvol:v3.28.1

# NRI plugins (CPU balloon policy)
docker pull $JFROG/ei-docker-virtual/containers/nri-plugins/nri-resource-policy-balloons:v0.12.2
docker pull $JFROG/ei-docker-virtual/containers/nri-plugins/nri-config-manager:v0.12.2

# Misc
docker pull $JFROG/ei-docker-virtual/library/nginx:1.25.2-alpine
docker pull $JFROG/ei-docker-virtual/bitnamilegacy/etcd:3.5.10-debian-11-r2
docker pull $JFROG/ei-docker-virtual/ubuntu:22.04
docker pull $JFROG/ei-docker-virtual/rancher/local-path-provisioner:v0.0.24
```

**Images that require manual push** (old tags not available via JFrog remote):

```bash
# busybox:1.28 — Docker Hub v2 API drops very old tags
docker pull $JFROG/ei-docker-virtual/library/busybox:latest
docker tag <sha> $JFROG/ei-docker/library/busybox:1.28
docker push $JFROG/ei-docker/library/busybox:1.28

# apisix-ingress-controller:1.8.0 — requires Docker Hub login
docker login -u <dockerhub-user> -p <pat>
docker pull docker.io/apache/apisix-ingress-controller:1.8.0
docker tag apache/apisix-ingress-controller:1.8.0 $JFROG/ei-docker/apache/apisix-ingress-controller:1.8.0
docker push $JFROG/ei-docker/apache/apisix-ingress-controller:1.8.0
```

### 3b — Helm Charts

Download and upload charts to `ei-helm-local`:

```bash
JFROG_URL=http://100.67.152.212:8082/artifactory
JFROG_CREDS=admin:password

# Add upstream repos
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm repo add langfuse https://langfuse.github.io/langfuse-k8s
helm repo add apisix https://charts.apiseven.com
helm repo add nri-plugins https://containers.github.io/nri-plugins
helm repo update

# Pull chart tarballs
helm pull ingress-nginx/ingress-nginx --version 4.12.2
helm pull langfuse/langfuse --version 1.5.1
helm pull apisix/apisix --version 2.8.1
helm pull nri-plugins/nri-resource-policy-balloons --version v0.12.2

# Download Keycloak chart (Bitnami OCI)
helm pull oci://registry-1.docker.io/bitnamicharts/keycloak --version 22.1.0
helm pull oci://registry-1.docker.io/bitnamicharts/postgresql --version 16.7.4
helm pull oci://registry-1.docker.io/bitnamicharts/redis --version 21.1.3
helm pull oci://registry-1.docker.io/bitnamicharts/clickhouse --version 8.0.5
helm pull oci://registry-1.docker.io/bitnamicharts/minio --version 14.10.5
helm pull oci://registry-1.docker.io/bitnamicharts/valkey --version 2.2.4

# Upload all tarballs to JFrog via HTTP
for chart in *.tgz; do
  curl -u $JFROG_CREDS -T "$chart" "$JFROG_URL/ei-helm-local/$chart"
done

# Generate and upload index.yaml (REQUIRED — JFrog does not auto-generate it)
helm repo index . --url $JFROG_URL/ei-helm-local
curl -u $JFROG_CREDS -T index.yaml "$JFROG_URL/ei-helm-local/index.yaml"
```

Verify:
```bash
helm repo add ei-helm $JFROG_URL/ei-helm-local --force-update
helm search repo ei-helm
```

### 3c — PyPI Packages

```bash
pip download ansible==9.8.0 ansible-core==2.16.9 \
  jmespath==1.0.1 jsonschema==4.23.0 netaddr==1.3.0 \
  kubernetes==31.0.0 pyyaml==6.0.2 cryptography requests \
  oauthlib requests-oauthlib urllib3 certifi charset-normalizer \
  idna packaging typing-extensions six python-dateutil \
  jsonpatch jsonpointer attrs rpds-py referencing \
  -d /tmp/wheels/

# Upload each wheel to JFrog
for whl in /tmp/wheels/*.whl /tmp/wheels/*.tar.gz; do
  curl -u $JFROG_CREDS -T "$whl" "$JFROG_URL/ei-pypi-local/$(basename $whl)"
done
```

### 3d — Ansible Collections

```bash
ansible-galaxy collection download kubernetes.core:6.3.0 \
  community.kubernetes:2.0.1 community.general:12.5.0 ansible.posix \
  -p /tmp/collections/

for tarball in /tmp/collections/*.tar.gz; do
  fname=$(basename $tarball)
  # Rename to expected format: <namespace>-<name>-latest.tar.gz
  curl -u $JFROG_CREDS -T "$tarball" "$JFROG_URL/ei-generic-binaries/ansible-collections/$fname"
done
```

### 3e — Kubernetes Binaries (for Kubespray)

Upload binaries to `ei-generic-binaries` preserving the original URL path structure:

```bash
# Kubernetes binaries
for bin in kubeadm kubectl kubelet; do
  curl -LO https://dl.k8s.io/release/v1.30.4/bin/linux/amd64/$bin
  curl -u $JFROG_CREDS -T $bin "$JFROG_URL/ei-generic-binaries/dl.k8s.io/release/v1.30.4/bin/linux/amd64/$bin"
done

# CNI plugins
curl -LO https://github.com/containernetworking/plugins/releases/download/v1.4.0/cni-plugins-linux-amd64-v1.4.0.tgz
curl -u $JFROG_CREDS -T cni-plugins-linux-amd64-v1.4.0.tgz \
  "$JFROG_URL/ei-generic-binaries/github.com/containernetworking/plugins/releases/download/v1.4.0/cni-plugins-linux-amd64-v1.4.0.tgz"

# containerd, runc, crictl, etcd, helm, calico — same pattern
# See CLAUDE.md for full list of binary versions and paths
```

### 3f — LLM Model Files

```bash
# Download model from HuggingFace (requires HF token)
pip install huggingface_hub
python3 -c "
from huggingface_hub import snapshot_download
snapshot_download(
  'meta-llama/Llama-3.1-8B-Instruct',
  local_dir='/tmp/Llama-3.1-8B-Instruct',
  token='hf_...'
)
"

# Upload all model files to JFrog ei-generic-models
find /tmp/Llama-3.1-8B-Instruct -type f | while read f; do
  rel=${f#/tmp/Llama-3.1-8B-Instruct/}
  curl -u $JFROG_CREDS -T "$f" "$JFROG_URL/ei-generic-models/Meta-Llama-3.1-8B-Instruct/$rel"
done
```

### 3g — Kubespray and Binaries

```bash
# kubespray tarball
git clone https://github.com/kubernetes-sigs/kubespray
cd kubespray && git checkout v2.27.0 && cd ..
tar -czf kubespray.tar.gz kubespray/
curl -u $JFROG_CREDS -T kubespray.tar.gz "$JFROG_URL/ei-generic-binaries/kubespray.tar.gz"

# helm binary
curl -LO https://get.helm.sh/helm-v3.15.4-linux-amd64.tar.gz
curl -u $JFROG_CREDS -T helm-v3.15.4-linux-amd64.tar.gz \
  "$JFROG_URL/ei-generic-binaries/get.helm.sh/helm-v3.15.4-linux-amd64.tar.gz"
```

### 3h — Set JFrog Repos to Offline

Once all assets are cached, set all remote repos to **Offline** in JFrog UI:
- Admin → Repositories → Edit each remote repo → Advanced → Set to Offline

This enforces true airgap: JFrog serves only cached content and refuses new internet fetches.

---

## Step 4 — Verify and Disable Internet on VM2

### Check current internet access

```bash
curl -s --max-time 5 https://google.com && echo "HAS INTERNET" || echo "NO INTERNET"
curl -s --max-time 5 https://huggingface.co && echo "HAS INTERNET" || echo "NO INTERNET"
```

### Block internet (allow only LAN and loopback)

```bash
# Install iptables-persistent so rules survive reboots
sudo apt-get install -y iptables-persistent

# Allow loopback, LAN, and JFrog VM1
sudo iptables -F OUTPUT
sudo iptables -I OUTPUT 1 -o lo -j ACCEPT
sudo iptables -I OUTPUT 2 -d 127.0.0.0/8 -j ACCEPT
sudo iptables -I OUTPUT 3 -d 10.0.0.0/8 -j ACCEPT
sudo iptables -I OUTPUT 4 -d 100.67.0.0/16 -j ACCEPT   # LAN subnet
sudo iptables -I OUTPUT 5 -d 192.168.0.0/16 -j ACCEPT
sudo iptables -A OUTPUT -j DROP

# Save rules so they persist across reboots
sudo netfilter-persistent save
```

### Verify airgap

```bash
curl -s --max-time 5 https://google.com && echo "FAIL - internet still open" || echo "OK - internet blocked"
curl -s --max-time 5 http://100.67.152.212:8082/artifactory/api/system/ping && echo "OK - JFrog reachable" || echo "FAIL - JFrog unreachable"
```

---

## Step 5 — Copy Git Repo to VM2

From a machine with access to both the repo and VM2:

```bash
# Clone the repo
git clone <repo-url> Enterprise-Inference
cd Enterprise-Inference

# SCP to VM2
scp -r Enterprise-Inference user@<VM2-IP>:~/
```

Or copy via USB/shared storage in a fully disconnected environment.

**After copying, strip Windows CRLF line endings** (if copied from a Windows machine):

```bash
find ~/Enterprise-Inference -name "*.sh" -o -name "*.yml" -o -name "*.yaml" -o -name "*.cfg" | \
  xargs sed -i 's/\r//'
```

---

## Step 6 — Deploy Enterprise Inference

### 6a — Configure `inference-config.cfg`

```bash
vi ~/Enterprise-Inference/core/inventory/inference-config.cfg
```

Key settings for airgap:

```ini
cluster_url=api.example.com
cert_file=~/certs/cert.pem
key_file=~/certs/key.pem
keycloak_client_id=my-client-id
keycloak_admin_user=your-keycloak-admin-user
keycloak_admin_password=changeme
hugging_face_token=hf_...
models=meta-llama/Llama-3.1-8B-Instruct
cpu_or_gpu=cpu

# Airgap settings — must be set to on
airgap_enabled=on
jfrog_url=http://100.67.152.212:8082/artifactory
jfrog_username=admin
jfrog_password=password

# Note: deploy_nri_balloon_policy=no does NOT reliably suppress NRI.
# ballon-policy.sh had a bypass bug (|| cpu_or_gpu == "c") that triggered NRI
# for all CPU deployments regardless of this variable.
# The real fix is the code change in core/lib/xeon/ballon-policy.sh — see Known Issues.
```

### 6b — Apply single-node inventory

```bash
cp ~/Enterprise-Inference/docs/examples/single-node/hosts.yaml \
   ~/Enterprise-Inference/core/inventory/hosts.yaml
```

Then update `ansible_user` to match the deployment user:

```bash
sed -i -E "/^[[:space:]]*master1:/,/^[[:space:]]{2}children:/ \
  s/^([[:space:]]*ansible_user:[[:space:]]*).*/\1$(whoami)/" \
  ~/Enterprise-Inference/core/inventory/hosts.yaml
```

### 6c — Generate SSL certificates

```bash
mkdir -p ~/certs
openssl req -x509 -newkey rsa:4096 \
  -keyout ~/certs/key.pem \
  -out ~/certs/cert.pem \
  -days 365 -nodes \
  -subj '/CN=api.example.com'
```

These paths are referenced in `inference-config.cfg` as `cert_file` and `key_file`.

### 6d — Add VM2 hosts entry for `api.example.com`

```bash
echo "$(hostname -I | awk '{print $1}') api.example.com" | sudo tee -a /etc/hosts
```

### 6e — Run the deployment

```bash
cd ~/Enterprise-Inference
bash inference-stack-deploy.sh
```

The deployment will:
1. Install prerequisites (pip from JFrog PyPI, ansible collections from JFrog)
2. Download Kubespray from JFrog
3. Deploy Kubernetes via Kubespray (all binaries and images from JFrog)
4. Deploy ingress-nginx, Keycloak, APISIX
5. Deploy vLLM model pods

### 6f — Monitor deployment

```bash
# Watch pods come up
kubectl get pods -w

# Check vLLM pod logs (model loading)
kubectl logs <vllm-pod-name> --tail=20 | grep -v "OMP tid"
```

**Expected pod states when complete:**

```
keycloak-0                    1/1 Running
keycloak-postgresql-0         1/1 Running
vllm-llama-3-2-3b-cpu-*       1/1 Running
vllm-llama-8b-cpu-*           1/1 Running
```

---

## Step 7 — Test Inference

### 7a — Generate Keycloak token

The APISIX gateway is exposed on NodePort `32353` (HTTP). Keycloak admin API is accessed via port-forward:

```bash
# Start port-forward to Keycloak admin API (run in background)
kubectl port-forward svc/keycloak 8080:80 &

# Source the token script
cd ~/Enterprise-Inference/core
. scripts/generate-token.sh

echo "TOKEN=$TOKEN"
```

### 7b — Verify models are available

```bash
curl -s http://api.example.com:32353/Llama-3.2-3B-Instruct-vllmcpu/v1/models \
  -H "Authorization: Bearer $TOKEN" | jq .

curl -s http://api.example.com:32353/Llama-3.1-8B-Instruct-vllmcpu/v1/models \
  -H "Authorization: Bearer $TOKEN" | jq .
```

### 7c — Test inference (completions)

```bash
curl -s http://api.example.com:32353/Llama-3.2-3B-Instruct-vllmcpu/v1/completions \
  -X POST \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "model": "meta-llama/Llama-3.2-3B-Instruct",
    "prompt": "What is Deep Learning?",
    "max_tokens": 100,
    "temperature": 0
  }' | jq .choices[0].text
```

```bash
curl -s http://api.example.com:32353/Llama-3.1-8B-Instruct-vllmcpu/v1/completions \
  -X POST \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "model": "meta-llama/Llama-3.1-8B-Instruct",
    "prompt": "What is Deep Learning?",
    "max_tokens": 100,
    "temperature": 0
  }' | jq .choices[0].text
```

---

## Known Issues and Fixes

### vLLM pods stuck at 0/1 in airgap (HuggingFace network timeout)

**Symptom**: Pod is `0/1 Running`, logs stop after OMP thread binding, no model files open.

**Root cause**: `HF_HUB_OFFLINE` is not set. HuggingFace Hub library attempts network calls to `huggingface.co` to validate cached model files. In airgap these calls hang silently.

**Fix**: Add to the model's ConfigMap:
```bash
kubectl patch configmap <model>-config --type=merge \
  -p '{"data":{"HF_HUB_OFFLINE":"1","TRANSFORMERS_OFFLINE":"1"}}'
kubectl rollout restart deployment <model>
```

**Permanent fix**: Add to `core/helm-charts/vllm/xeon-values.yaml` under `defaultModelConfigs.configMapValues`.

### Model files not in HuggingFace Hub cache format

If model files were manually downloaded (not via `snapshot_download()`), the Hub cache metadata is incomplete and vLLM cannot find the files even with `HF_HUB_OFFLINE=1`.

**Proper fix**: Pre-populate PVCs using `huggingface_hub.snapshot_download()` via an init container or Ansible task before vLLM starts, pointing `HF_ENDPOINT` to JFrog `ei-generic-models`.

### NRI Balloon Policy auto-enabled for CPU deployments (3 bugs)

Three compounding bugs caused NRI balloon policy to deploy on all CPU deployments regardless of config:

1. **`parse-user-prompts.sh`** — silently auto-sets `deploy_nri_balloon_policy="yes"` for any CPU deployment when the variable is unset
2. **`core/lib/xeon/ballon-policy.sh`** — contained `|| [ "$cpu_or_gpu" == "c" ]` bypass that triggered NRI deployment for all CPU regardless of `deploy_nri_balloon_policy` value — **setting `deploy_nri_balloon_policy=no` in config never suppressed this**
3. **`deploy-inference-models.yml`** — all 7 model install tasks unconditionally passed `--set cpu_balloon_annotation` to helm

**Fix (code changes required)**:
- `ballon-policy.sh`: remove the `|| [ "$cpu_or_gpu" == "c" ]` clause from the condition
- `deploy-inference-models.yml`: guard `--set cpu_balloon_annotation` with `{% if enable_cpu_balloons | default(false) | bool %}` in all 7 model tasks

### Docker Hub rate limits when pre-caching images

**Fix**: `docker login -u <user> -p <pat>` before pulling; rotate PAT after use.

### JFrog "manifest unknown" for very old image tags

Docker Hub v2 API drops manifests for tags like `busybox:1.28`. JFrog remote cannot fetch them.

**Fix**: Pull equivalent tag, retag, push to `ei-docker` local:
```bash
docker pull 100.67.152.212:8082/ei-docker-virtual/library/busybox:latest
docker tag <sha> 100.67.152.212:8082/ei-docker/library/busybox:1.28
docker push 100.67.152.212:8082/ei-docker/library/busybox:1.28
```

### containerd mirror `skip_verify` breaks HTTP mirrors

Do NOT set `skip_verify: false` in `hosts.toml` — any presence of `skip_verify` triggers containerd's HTTPS-first behavior which fails for HTTP JFrog.
