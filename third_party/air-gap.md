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

## Step 1  -  Install JFrog Artifactory on VM1 (internet-connected)

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

## Step 2  -  Create Repositories in JFrog

Create the following repositories via Admin → Repositories → Add Repository:

### Docker Repositories

| Name | Type | Remote URL | Notes |
|---|---|---|---|
| `ei-docker-local` | Local |  -  | Manually pushed images (old tags, rate-limited, not in any remote) |
| `ei-docker-dockerhub` | Remote | `https://registry-1.docker.io` | Bitnami, Langfuse, etcd, nginx |
| `ei-docker-ecr` | Remote | `https://public.ecr.aws` | vLLM CPU image |
| `ei-docker-ghcr` | Remote | `https://ghcr.io` | TGI, TEI, LiteLLM, NRI plugins |
| `ei-docker-k8s` | Remote | `https://registry.k8s.io` | Kubernetes components |
| `ei-docker-quay` | Remote | `https://quay.io` | Calico |
| `ei-docker-virtual` | Virtual | - | Members: `ei-docker-local`, `ei-docker-dockerhub`, `ei-docker-ecr`, `ei-docker-ghcr`, `ei-docker-k8s`, `ei-docker-quay` |

**Create `ei-docker-local` and add to virtual repo via API** (or use JFrog UI):
```bash
# Create local Docker repo
curl -s -u admin:password -X PUT "http://100.67.152.212:8082/artifactory/api/repositories/ei-docker-local" \
  -H "Content-Type: application/json" -d '{"rclass":"local","packageType":"docker"}'

# Update virtual repo to include ei-docker-local first (so locally pushed images take precedence)
curl -s -u admin:password -X POST "http://100.67.152.212:8082/artifactory/api/repositories/ei-docker-virtual" \
  -H "Content-Type: application/json" \
  -d '{"rclass":"virtual","packageType":"docker","repositories":["ei-docker-local","ei-docker-dockerhub","ei-docker-ecr","ei-docker-ghcr","ei-docker-k8s","ei-docker-quay"]}'
```

### Helm Repository

| Name | Type | Remote URL | Notes |
|---|---|---|---|
| `ei-helm-local` | Local (HelmOCI) |  -  | Charts uploaded as HTTP tarballs |
| `ei-helm-ingress-nginx` | Remote (HelmOCI) | `https://kubernetes.github.io/ingress-nginx` | Optional remote proxy |
| `ei-helm-langfuse` | Remote (HelmOCI) | `https://langfuse.github.io/langfuse-k8s` | Optional remote proxy |
| `ei-helm-virtual` | Virtual | - | Members: `ei-helm-local`, `ei-helm-ingress-nginx`, `ei-helm-langfuse` |

> **Important**: `ei-helm-local` is **HelmOCI** type in JFrog. Charts are uploaded via HTTP REST API and `index.yaml` must be manually generated and uploaded  -  JFrog does not auto-generate it for HelmOCI repos.

### PyPI Repository

| Name | Type | Remote URL | Notes |
|---|---|---|---|
| `ei-pypi-local` | Local | - | Manually uploaded wheels |
| `ei-pypi-remote` | Remote | `https://pypi.org` | Internet proxy |
| `ei-pypi-virtual` | Virtual | - | Members: `ei-pypi-local`, `ei-pypi-remote` |

### Debian Repository

| Name | Type | Remote URL | Notes |
|---|---|---|---|
| `ei-debian-ubuntu` | Remote | `http://archive.ubuntu.com/ubuntu` | Ubuntu/Debian apt packages |
| `ei-debian-virtual` | Virtual | - | Members: `ei-debian-ubuntu` |

> Used by `setup-env.sh` to auto-configure `/etc/apt/sources.list` on VM2 in airgap mode. JFrog proxies the package index but **does not serve actual `.deb` files**  -  see Known Issues.

### HuggingFace Repository

| Name | Type | Notes |
|---|---|---|
| `ei-hf-remote` | Remote | Remote proxy → `huggingface.co` |
| `ei-hf-virtual` | Virtual | - | Members: `ei-hf-remote` |

> Used for caching HuggingFace model files if `HF_ENDPOINT` is pointed at JFrog.

### Generic Repository

| Name | Type | Contents |
|---|---|---|
| `ei-generic-binaries` | Local | kubectl, helm, kubespray, ansible collections, Kubernetes binaries, pip.whl, apt-debs/ |
| `ei-generic-models` | Local | LLM model files (~30 GB) |

---

## Step 3  -  Pre-load All Required Assets into JFrog

All commands below run on **VM1** (internet access).

### 3a  -  Docker Images (cache via JFrog remote repos)

Pull each image through JFrog so it gets cached in the remote repo:

```bash
JFROG=100.67.152.212:8082

# vLLM CPU
docker pull $JFROG/ei-docker-virtual/q9t5s3a7/vllm-cpu-release-repo:v0.10.2

# GenAI Gateway (TGI, TEI, LiteLLM)  -  needed if deploy_genai_gateway=on
docker pull $JFROG/ei-docker-virtual/ghcr.io/huggingface/text-generation-inference:2.4.0-intel-cpu
docker pull $JFROG/ei-docker-virtual/ghcr.io/huggingface/text-embeddings-inference:cpu-1.7
docker pull $JFROG/ei-docker-virtual/ghcr.io/berriai/litellm-non_root:main-v1.75.8-stable

# Langfuse (observability)  -  needed if deploy_observability=on
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
docker pull $JFROG/ei-docker-virtual/library/registry:2
docker pull $JFROG/ei-docker-virtual/bitnamilegacy/etcd:3.5.10-debian-11-r2
docker pull $JFROG/ei-docker-virtual/ubuntu:22.04
docker pull $JFROG/ei-docker-virtual/rancher/local-path-provisioner:v0.0.24

# Kubernetes Dashboard (deploy_cluster_dashboard tag)
docker pull $JFROG/ei-docker-virtual/kubernetesui/dashboard:v2.7.0
docker pull $JFROG/ei-docker-virtual/kubernetesui/metrics-scraper:v1.0.8

# OpenVINO Model Server (needed if deploy_openvino=on)
docker pull $JFROG/ei-docker-virtual/openvino/model_server:latest
```

> **Note on `bitnamicharts/*` in the JFrog catalog**: These entries (`bitnamicharts/postgresql`, `bitnamicharts/redis`, etc.) are OCI Helm chart layers stored as Docker artifacts  -  they appear automatically when `helm pull oci://...` is run. They are **not** Docker runtime images and do not need separate `docker pull` commands.

> **Images not yet in JFrog** (needed for full deployment with all features on):
> - `berriai/litellm-non_root:main-v1.75.8-stable` (ghcr.io)  -  required if `deploy_genai_gateway=on`
> - `langfuse/langfuse:3.106.1` and `langfuse/langfuse-worker:3.106.1`  -  required if `deploy_observability=on`
> - `bitnamilegacy/zookeeper:3.9.3-debian-12-r8`  -  required if Zookeeper enabled
> - `bitnami/mc:2024.12.18` (MinIO client)  -  required if MinIO enabled
>
> Pre-cache these on VM1 before enabling those features:
> ```bash
> docker pull $JFROG/ei-docker-virtual/ghcr.io/berriai/litellm-non_root:main-v1.75.8-stable
> docker pull $JFROG/ei-docker-virtual/langfuse/langfuse:3.106.1
> docker pull $JFROG/ei-docker-virtual/langfuse/langfuse-worker:3.106.1
> docker pull $JFROG/ei-docker-virtual/bitnamilegacy/zookeeper:3.9.3-debian-12-r8
> docker pull $JFROG/ei-docker-virtual/bitnami/mc:2024.12.18
> ```

**Images that require manual push to `ei-docker-local`** (old tags or rate-limited images unavailable via JFrog remote):

```bash
# busybox:1.28  -  Docker Hub v2 API drops manifests for very old tags; JFrog remote returns "manifest unknown"
# Pull latest through JFrog (caches latest + 1.36), then retag as 1.28 and push to ei-docker-local
docker pull $JFROG/ei-docker-virtual/library/busybox:latest
docker tag $JFROG/ei-docker-virtual/library/busybox:latest $JFROG/ei-docker-local/library/busybox:1.28
docker push $JFROG/ei-docker-local/library/busybox:1.28

# apisix-ingress-controller:1.8.0  -  not cached in any remote; pull directly from Docker Hub
docker login -u <dockerhub-user> -p <pat>
docker pull docker.io/apache/apisix-ingress-controller:1.8.0
docker tag apache/apisix-ingress-controller:1.8.0 $JFROG/ei-docker-local/apache/apisix-ingress-controller:1.8.0
docker push $JFROG/ei-docker-local/apache/apisix-ingress-controller:1.8.0
```

Verify both images are present in JFrog:
```bash
curl -s -u admin:password http://$JFROG/artifactory/api/docker/ei-docker-virtual/v2/library/busybox/tags/list | jq .
# Expected: {"name":"library/busybox","tags":["1.28","1.36","latest","sha256__...",...]}

curl -s -u admin:password http://$JFROG/artifactory/api/docker/ei-docker-virtual/v2/apache/apisix-ingress-controller/tags/list | jq .
# Expected: {"name":"apache/apisix-ingress-controller","tags":["1.8.0"]}
```

**Ensuring `nginx:1.25.2-alpine` is fully cached** (manifest list alone is not enough):

After a tag pull, JFrog may only cache the multi-arch manifest list  -  not the amd64-specific manifest. containerd on VM2 will then fail with `manifest unknown`. Force full caching by pulling the amd64 digest explicitly:

```bash
# Pull by tag first (caches manifest list)
docker pull --platform linux/amd64 $JFROG/ei-docker-virtual/library/nginx:1.25.2-alpine

# Pull by amd64 digest to force caching of the platform-specific manifest + layers
docker pull $JFROG/ei-docker-virtual/library/nginx@sha256:fc2d39a0d6565db4bd6c94aa7b5efc2da67734cc97388afb5c72369a24bcfaea
```

Verify the image is properly cached (plain `curl` returns 404 even when cached  -  must use Docker Accept headers):
```bash
curl -s -u admin:password \
  -H "Accept: application/vnd.docker.distribution.manifest.v2+json" \
  -H "Accept: application/vnd.docker.distribution.manifest.list.v2+json" \
  -o /dev/null -w "%{http_code}" \
  "http://100.67.152.212:8082/v2/ei-docker-virtual/library/nginx/manifests/1.25.2-alpine"
# Must return 200
```

### 3b  -  Helm Charts

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
# Note: NRI chart downloads as nri-resource-policy-balloons-helm-chart-v0.12.2.tgz (non-standard name)

# Download Bitnami charts (OCI from Docker Hub)
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

# Generate and upload index.yaml (REQUIRED  -  JFrog does not auto-generate it)
helm repo index . --url $JFROG_URL/ei-helm-local
curl -u $JFROG_CREDS -T index.yaml "$JFROG_URL/ei-helm-local/index.yaml"
```

Verify all 10 charts are present:
```bash
curl -s -u admin:password "http://100.67.152.212:8082/artifactory/api/storage/ei-helm-local" | jq '.children[].uri'
# Expected (confirmed ):
# "/apisix-2.8.1.tgz"
# "/clickhouse-8.0.5.tgz"
# "/index.yaml"
# "/ingress-nginx-4.12.2.tgz"
# "/keycloak-22.1.0.tgz"
# "/langfuse-1.5.1.tgz"
# "/minio-14.10.5.tgz"
# "/nri-resource-policy-balloons-helm-chart-v0.12.2.tgz"
# "/postgresql-16.7.4.tgz"
# "/redis-21.1.3.tgz"
# "/valkey-2.2.4.tgz"

helm repo add ei-helm $JFROG_URL/ei-helm-local --force-update
helm search repo ei-helm
```

### 3c  -  PyPI Packages

```bash
pip download ansible==9.8.0 ansible-core==2.16.18 \
  jinja2 jmespath==1.0.1 jsonschema==4.23.0 jsonschema-specifications \
  netaddr==1.3.0 kubernetes==35.0.0 pyyaml==6.0.3 \
  cryptography requests oauthlib requests-oauthlib urllib3 \
  certifi charset-normalizer idna packaging typing-extensions \
  six python-dateutil attrs rpds-py referencing resolvelib \
  durationpy websocket-client cffi pycparser markupsafe \
  -d /tmp/wheels/

# Upload each wheel to JFrog
for whl in /tmp/wheels/*.whl /tmp/wheels/*.tar.gz; do
  curl -u $JFROG_CREDS -T "$whl" "$JFROG_URL/ei-pypi-local/$(basename $whl)"
done
```

**Confirmed packages in `ei-pypi-local`**:

```
ansible==9.8.0, ansible-core==2.16.18, attrs==26.1.0, certifi==2026.2.25,
cffi==2.0.0, charset-normalizer==3.4.7, cryptography==46.0.6, durationpy==0.10,
idna==3.11, jinja2==3.1.6, jmespath==1.0.1, jsonschema==4.23.0,
jsonschema-specifications==2025.9.1, kubernetes==35.0.0, markupsafe==3.0.3,
netaddr==1.3.0, oauthlib==3.3.1, packaging==26.0, pycparser==3.0,
python-dateutil==2.9.0.post0, pyyaml==6.0.3, referencing==0.37.0,
requests==2.33.1, requests-oauthlib==2.0.0, resolvelib==1.0.1,
rpds-py==0.30.0, six==1.17.0, typing-extensions==4.15.0,
urllib3==2.6.3, websocket-client==1.9.0
```

> **Not in JFrog** (not required for current deployment scope): `jsonpatch`, `jsonpointer` - add these if Ansible k8s patch operations are needed.

### 3d  -  pip Bootstrap Wheel

Ubuntu disables `ensurepip` by default, and `python3-pip` cannot be installed via apt in airgap. The deployment bootstraps pip from a wheel downloaded from JFrog:

```bash
pip download pip --no-deps -d /tmp/pip-dl/
curl -u $JFROG_CREDS -T /tmp/pip-dl/pip-*.whl "$JFROG_URL/ei-generic-binaries/pip.whl"
```

> JFrog stores it as `pip.whl` (generic name). The deployment script reads the version/tag from the wheel's WHEEL metadata and renames it to the proper format (e.g. `pip-26.0.1-py3-none-any.whl`) before installing.

### 3e  -  Ansible Collections

`setup-env.sh` downloads collections from JFrog using the pattern `<namespace>-<name>-latest.tar.gz`. Files **must be uploaded with the `-latest` suffix** or they will be silently skipped.

```bash
ansible-galaxy collection download kubernetes.core:6.3.0 \
  community.general:12.5.0 ansible.posix \
  -p /tmp/collections/

# Upload with -latest suffix (required  -  setup-env.sh looks for <namespace>-<name>-latest.tar.gz)
curl -u $JFROG_CREDS -T /tmp/collections/kubernetes-core-6.3.0.tar.gz \
  "$JFROG_URL/ei-generic-binaries/ansible-collections/kubernetes-core-latest.tar.gz"
curl -u $JFROG_CREDS -T /tmp/collections/community-general-12.5.0.tar.gz \
  "$JFROG_URL/ei-generic-binaries/ansible-collections/community-general-latest.tar.gz"
curl -u $JFROG_CREDS -T /tmp/collections/ansible-posix-*.tar.gz \
  "$JFROG_URL/ei-generic-binaries/ansible-collections/ansible-posix-latest.tar.gz"
```

> **Warning**: The current JFrog contents have a filename mismatch  -  `community-general-12.5.0.tar.gz` and `kubernetes-core-6.3.0.tar.gz` use versioned names instead of `-latest`. Only `ansible-posix-latest.tar.gz` matches the expected pattern. The others are silently skipped by `setup-env.sh` (it warns but does not fail). Re-upload with `-latest` suffix if collections are not being installed.

**Confirmed in `ei-generic-binaries/ansible-collections/`** ( verified):
```
ansible-posix-latest.tar.gz       ← correct name, will be installed
community-general-12.5.0.tar.gz   ← wrong name, skipped by setup-env.sh
community-kubernetes-2.0.1.tar.gz ← deprecated, not needed
kubernetes-core-6.3.0.tar.gz      ← wrong name, skipped by setup-env.sh
```

### 3f  -  apt `.deb` Files for jq

JFrog's Debian remote proxies the package index but **returns 404 for actual `.deb` file downloads**. The `inference-tools` role installs `jq` in airgap by downloading `.deb` files directly from `ei-generic-binaries`. Upload these on VM1:

```bash
# Download the required debs on VM1
apt-get download jq libjq1 libonig5

# Upload to JFrog
curl -u $JFROG_CREDS -T jq_1.6-2.1ubuntu3.1_amd64.deb "$JFROG_URL/ei-generic-binaries/apt-debs/jq_1.6-2.1ubuntu3.1_amd64.deb"
curl -u $JFROG_CREDS -T libjq1_1.6-2.1ubuntu3.1_amd64.deb "$JFROG_URL/ei-generic-binaries/apt-debs/libjq1_1.6-2.1ubuntu3.1_amd64.deb"
curl -u $JFROG_CREDS -T libonig5_6.9.7.1-2build1_amd64.deb "$JFROG_URL/ei-generic-binaries/apt-debs/libonig5_6.9.7.1-2build1_amd64.deb"
```

Verify:
```bash
curl -s -u $JFROG_CREDS "$JFROG_URL/ei-generic-binaries/apt-debs/" | grep -o 'jq[^"]*\.deb'
```

### 3g  -  Kubernetes Binaries (for Kubespray)

Upload binaries to `ei-generic-binaries` preserving the original URL path structure (Kubespray constructs download URLs that must match exactly):

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

# crictl
curl -LO https://github.com/kubernetes-sigs/cri-tools/releases/download/v1.30.0/crictl-v1.30.0-linux-amd64.tar.gz
curl -u $JFROG_CREDS -T crictl-v1.30.0-linux-amd64.tar.gz \
  "$JFROG_URL/ei-generic-binaries/github.com/kubernetes-sigs/cri-tools/releases/download/v1.30.0/crictl-v1.30.0-linux-amd64.tar.gz"

# etcd
curl -LO https://github.com/etcd-io/etcd/releases/download/v3.5.12/etcd-v3.5.12-linux-amd64.tar.gz
curl -u $JFROG_CREDS -T etcd-v3.5.12-linux-amd64.tar.gz \
  "$JFROG_URL/ei-generic-binaries/github.com/etcd-io/etcd/releases/download/v3.5.12/etcd-v3.5.12-linux-amd64.tar.gz"

# Calico binaries
curl -LO https://github.com/projectcalico/calico/releases/download/v3.28.1/calicoctl-linux-amd64
curl -u $JFROG_CREDS -T calicoctl-linux-amd64 \
  "$JFROG_URL/ei-generic-binaries/github.com/projectcalico/calico/releases/download/v3.28.1/calicoctl-linux-amd64"
curl -LO https://github.com/projectcalico/calico/archive/v3.28.1.tar.gz
curl -u $JFROG_CREDS -T v3.28.1.tar.gz \
  "$JFROG_URL/ei-generic-binaries/github.com/projectcalico/calico/archive/v3.28.1.tar.gz"

# containerd
curl -LO https://github.com/containerd/containerd/releases/download/v1.7.21/containerd-1.7.21-linux-amd64.tar.gz
curl -u $JFROG_CREDS -T containerd-1.7.21-linux-amd64.tar.gz \
  "$JFROG_URL/ei-generic-binaries/github.com/containerd/containerd/releases/download/v1.7.21/containerd-1.7.21-linux-amd64.tar.gz"

# runc
curl -LO https://github.com/opencontainers/runc/releases/download/v1.1.13/runc.amd64
curl -u $JFROG_CREDS -T runc.amd64 \
  "$JFROG_URL/ei-generic-binaries/github.com/opencontainers/runc/releases/download/v1.1.13/runc.amd64"

# helm tarball (for inference-tools role airgap install)
curl -LO https://get.helm.sh/helm-v3.15.4-linux-amd64.tar.gz
curl -u $JFROG_CREDS -T helm-v3.15.4-linux-amd64.tar.gz \
  "$JFROG_URL/ei-generic-binaries/get.helm.sh/helm-v3.15.4-linux-amd64.tar.gz"
```

**Additional standalone binaries** (uploaded directly at root of `ei-generic-binaries`):
```bash
# kubectl, helm, yq, kubectx, kubens  -  for use on bastion/control node
curl -u $JFROG_CREDS -T kubectl "$JFROG_URL/ei-generic-binaries/kubectl"
curl -u $JFROG_CREDS -T helm "$JFROG_URL/ei-generic-binaries/helm"
curl -u $JFROG_CREDS -T yq "$JFROG_URL/ei-generic-binaries/yq"
curl -u $JFROG_CREDS -T kubectx "$JFROG_URL/ei-generic-binaries/kubectx"
curl -u $JFROG_CREDS -T kubens "$JFROG_URL/ei-generic-binaries/kubens"

# get-pip.py (alternative pip bootstrap  -  pip.whl is the primary method)
curl -LO https://bootstrap.pypa.io/get-pip.py
curl -u $JFROG_CREDS -T get-pip.py "$JFROG_URL/ei-generic-binaries/get-pip.py"
```

**Confirmed in `ei-generic-binaries/`** ( verified):
```
ansible-collections/    apt-debs/    dl.k8s.io/    get.helm.sh/    github.com/
get-pip.py    helm    kubectl    kubectx    kubens    kubespray.tar.gz    pip.whl    yq
```

**Confirmed in `ei-generic-binaries/dl.k8s.io/release/v1.30.4/bin/linux/amd64/`** ( verified):
```
kubeadm    kubectl    kubelet
```

**Confirmed in `ei-generic-binaries/apt-debs/`** ( verified):
```
jq_1.6-2.1ubuntu3.1_amd64.deb    libjq1_1.6-2.1ubuntu3.1_amd64.deb    libonig5_6.9.7.1-2build1_amd64.deb
```

### 3f  -  LLM Model Files

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

### 3g  -  Kubespray and Binaries

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

### 3h  -  Set JFrog Repos to Offline

Once all assets are cached, set all remote repos to **Offline** in JFrog UI:
- Admin → Repositories → Edit each remote repo → Advanced → Set to Offline

This enforces true airgap: JFrog serves only cached content and refuses new internet fetches.

---

## Step 4  -  Verify and Disable Internet on VM2

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

## Step 5  -  Copy Git Repo to VM2

From a machine with access to both the repo and VM2:

```bash
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

## Step 6  -  Deploy Enterprise Inference

### 6a  -  Configure `inference-config.cfg`

```bash
vi ~/Enterprise-Inference/core/inventory/inference-config.cfg
```

```
cluster_url=api.example.com
cert_file=~/certs/cert.pem
key_file=~/certs/key.pem
keycloak_client_id=my-client-id
keycloak_admin_user=your-keycloak-admin-user
keycloak_admin_password=changeme
hugging_face_token=hf_your_token_here
hugging_face_token_falcon3=your_hugging_face_token
models=
cpu_or_gpu=cpu
vault_pass_code=place-holder-123
deploy_kubernetes_fresh=on
deploy_ingress_controller=on
deploy_keycloak_apisix=on
deploy_genai_gateway=off
deploy_observability=off
deploy_llm_models=on
deploy_ceph=off
deploy_istio=off
uninstall_ceph=off
deploy_nri_balloon_policy=no
# Agentic AI Plugin
deploy_agenticai_plugin=off

# ---------------------------------------------------------------------------
# Airgap Configuration
# Set airgap_enabled=on to route all Helm repos through JFrog on VM1.
# Set airgap_enabled=off for standard internet-connected deployments.
# ---------------------------------------------------------------------------
airgap_enabled=on
jfrog_url=http://100.67.152.212:8082/artifactory
jfrog_username=admin
jfrog_password=password
```

### 6b  -  Apply single-node inventory

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

### 6c  -  Generate SSL certificates

```bash
mkdir -p ~/certs
openssl req -x509 -newkey rsa:4096 \
  -keyout ~/certs/key.pem \
  -out ~/certs/cert.pem \
  -days 365 -nodes \
  -subj '/CN=api.example.com'
```

These paths are referenced in `inference-config.cfg` as `cert_file` and `key_file`.

### 6d  -  Add VM2 hosts entry for `api.example.com`

```bash
echo "$(hostname -I | awk '{print $1}') api.example.com" | sudo tee -a /etc/hosts
```

### 6e  -  Run the deployment

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

### 6f  -  Monitor deployment

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
vllm-llama-8b-cpu-*           1/1 Running
```

---

## Step 7  -  Test Inference

### 7a  -  Generate Keycloak token

The APISIX gateway is exposed on NodePort `32353` (HTTP). Keycloak admin API is accessed via port-forward:

```bash
# Source the token script
cd ~/Enterprise-Inference/core
. scripts/generate-token.sh

```

### 7b  -  Verify models are available

```bash
curl -s http://api.example.com:32353/Llama-3.1-8B-Instruct-vllmcpu/v1/models \
  -H "Authorization: Bearer $TOKEN" | jq .
```

### 7c  -  Test inference (completions)

```bash
curl -k https://${BASE_URL}/Llama-3.1-8B-Instruct-vllmcpu/v1/completions\
  -X POST\
  -H "Content-Type: application/json"\
  -H "Authorization: Bearer $TOKEN"\
  -d '{
    "model": "meta-llama/Llama-3.1-8B-Instruct",
    "prompt": "What is Deep Learning?",
    "max_tokens": 25,
    "temperature": 0
  }'
```

---

For troubleshooting common failures, see [air-gap-troubleshooting.md](air-gap-troubleshooting.md).
