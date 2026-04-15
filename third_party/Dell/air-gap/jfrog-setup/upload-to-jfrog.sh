#!/usr/bin/env bash
# Copyright (C) 2025-2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# jfrog-upload-all-assets.sh
#
# Pre-loads all assets required for an airgapped EI deployment into JFrog Artifactory.
# Run this script on VM1 (internet-connected) before deploying EI on VM2 (airgapped).
#
# Covers all of Step 3 in third_party/air-gap.md:
#   3a - Docker images (pull through JFrog remote + manual push for old tags)
#   3b - Helm charts
#   3c - PyPI packages
#   3d - pip bootstrap wheel
#   3e - Ansible collections
#   3f - apt .deb files for jq
#   3g - Kubernetes / Kubespray binaries
#   3h - LLM model files (optional, requires HuggingFace token)
#   3i - Kubespray tarball
#
# Usage:
#   ./jfrog-upload-all-assets.sh [OPTIONS]
#
# Options:
#   --jfrog-url URL        JFrog base URL (default: http://100.67.152.212:8082/artifactory)
#   --jfrog-user USER      JFrog username (default: admin)
#   --jfrog-pass PASS      JFrog password (default: password)
#   --hf-token TOKEN       HuggingFace token (required only for --step 3h)
#   --dockerhub-user USER  Docker Hub username (required for apisix-ingress-controller push)
#   --dockerhub-pass PASS  Docker Hub password/PAT
#   --step STEP            Run only a specific step (e.g. --step 3a, --step 3b, ...)
#   --skip STEP            Skip a specific step (repeatable)
#   --workdir DIR          Working directory for downloads (default: /tmp/ei-airgap-upload)
#   --install-prereqs      Install missing prerequisites (docker, helm, pip3, ansible) automatically
#   --dry-run              Print commands without executing them
#   -h, --help             Show this help message

set -euo pipefail

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
JFROG_URL="${JFROG_URL}"
JFROG_USER="${JFROG_USER}"
JFROG_PASS="${JFROG_PASS}"
HF_TOKEN="${HF_TOKEN}"
DOCKERHUB_USER="${DOCKER_TOKEN}"
DOCKERHUB_PASS="${DOCKER_PASS}"
ONLY_STEP=""
SKIP_STEPS=()
WORKDIR="/tmp/ei-airgap-upload"
DRY_RUN=false

# ---------------------------------------------------------------------------
# Colours
# ---------------------------------------------------------------------------
RED='\033[0;31m'; YELLOW='\033[1;33m'; GREEN='\033[0;32m'; CYAN='\033[0;36m'; NC='\033[0m'
info()    { echo -e "${CYAN}[INFO]${NC}  $*"; }
success() { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*" >&2; }
step()    { echo -e "\n${CYAN}========== $* ==========${NC}"; }

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------
while [[ $# -gt 0 ]]; do
  case $1 in
    --jfrog-url)      JFROG_URL="$2";       shift 2 ;;
    --jfrog-user)     JFROG_USER="$2";      shift 2 ;;
    --jfrog-pass)     JFROG_PASS="$2";      shift 2 ;;
    --hf-token)       HF_TOKEN="$2";        shift 2 ;;
    --dockerhub-user) DOCKERHUB_USER="$2";  shift 2 ;;
    --dockerhub-pass) DOCKERHUB_PASS="$2";  shift 2 ;;
    --step)           ONLY_STEP="$2";       shift 2 ;;
    --skip)           SKIP_STEPS+=("$2");   shift 2 ;;
    --workdir)        WORKDIR="$2";         shift 2 ;;
    --dry-run)        DRY_RUN=true;         shift ;;
    -h|--help)
      sed -n '/^# Usage:/,/^[^#]/p' "$0" | grep '^#' | sed 's/^# \?//'
      exit 0 ;;
    *) error "Unknown option: $1"; exit 1 ;;
  esac
done

# Derived
JFROG_CREDS="${JFROG_USER}:${JFROG_PASS}"
JFROG_HOST="${JFROG_URL#http://}"; JFROG_HOST="${JFROG_HOST#https://}"; JFROG_HOST="${JFROG_HOST%%/*}"
JFROG_DOCKER="${JFROG_HOST}"   # used as docker registry prefix

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
run() {
  if $DRY_RUN; then
    echo "[DRY-RUN] $*"
  else
    "$@"
  fi
}

should_run() {
  local step="$1"
  [[ -z "$ONLY_STEP" || "$ONLY_STEP" == "$step" ]] || return 1
  for s in "${SKIP_STEPS[@]:-}"; do [[ "$s" == "$step" ]] && return 1; done
  return 0
}

jfrog_upload() {
  # jfrog_upload <local-file> <jfrog-path>
  local file="$1" dest="$2"
  info "Uploading $(basename "$file") -> $dest"
  run curl -fsSL -u "$JFROG_CREDS" -T "$file" "$JFROG_URL/$dest"
}

check_prereqs() {
  local missing=()
  for cmd in curl docker helm pip3 ansible-galaxy git; do
    command -v "$cmd" &>/dev/null || missing+=("$cmd")
  done
  if [[ ${#missing[@]} -gt 0 ]]; then
    error "Missing required tools: ${missing[*]}"
    error "Install them on VM1 before running this script."
    exit 1
  fi
}

# ---------------------------------------------------------------------------
# Step 3a - Docker Images
# ---------------------------------------------------------------------------
step_3a() {
  step "3a - Docker Images"
  local jfrog="$JFROG_DOCKER"

  # All images pulled through JFrog virtual repo (caches in the matching remote repo)
  local images=(
    # vLLM CPU (public.ecr.aws)
    "ei-docker-virtual/q9t5s3a7/vllm-cpu-release-repo:v0.10.2"
    # GenAI Gateway (ghcr.io - no registry prefix in JFrog path)
    "ei-docker-virtual/huggingface/text-generation-inference:2.4.0-intel-cpu"
    "ei-docker-virtual/huggingface/text-embeddings-inference:cpu-1.7"
    "ei-docker-virtual/berriai/litellm-non_root:main-v1.75.8-stable"
    # Langfuse (docker.io)
    "ei-docker-virtual/langfuse/langfuse:3.106.1"
    "ei-docker-virtual/langfuse/langfuse-worker:3.106.1"
    # Keycloak + PostgreSQL (docker.io bitnami)
    "ei-docker-virtual/bitnamilegacy/keycloak:25.0.2-debian-12-r2"
    "ei-docker-virtual/bitnamilegacy/postgresql:16.3.0-debian-12-r23"
    "ei-docker-virtual/bitnamilegacy/postgresql:17.5.0-debian-12-r0"
    # Redis, MinIO, ClickHouse, Valkey, Zookeeper, os-shell (docker.io bitnami)
    "ei-docker-virtual/bitnamilegacy/redis:8.0.1-debian-12-r0"
    "ei-docker-virtual/bitnami/minio:2024.12.18"
    "ei-docker-virtual/bitnami/mc:2024.12.18"
    "ei-docker-virtual/bitnamilegacy/clickhouse:25.2.1-debian-12-r0"
    "ei-docker-virtual/bitnamilegacy/valkey:8.0.2-debian-12-r2"
    "ei-docker-virtual/bitnamilegacy/zookeeper:3.9.3-debian-12-r8"
    "ei-docker-virtual/bitnamilegacy/os-shell:12-debian-12-r48"
    # etcd (docker.io bitnami)
    "ei-docker-virtual/bitnamilegacy/etcd:3.5.10-debian-11-r2"
    # APISIX (docker.io)
    "ei-docker-virtual/apache/apisix:3.9.1-debian"
    # Ingress-nginx (registry.k8s.io)
    "ei-docker-virtual/ingress-nginx/controller:v1.12.2"
    "ei-docker-virtual/ingress-nginx/kube-webhook-certgen:v1.5.3"
    # Kubernetes core components (registry.k8s.io)
    "ei-docker-virtual/pause:3.10"
    "ei-docker-virtual/kube-apiserver:v1.30.4"
    "ei-docker-virtual/kube-controller-manager:v1.30.4"
    "ei-docker-virtual/kube-scheduler:v1.30.4"
    "ei-docker-virtual/kube-proxy:v1.30.4"
    "ei-docker-virtual/coredns/coredns:v1.11.1"
    "ei-docker-virtual/dns/k8s-dns-node-cache:1.22.28"
    "ei-docker-virtual/cpa/cluster-proportional-autoscaler:v1.8.8"
    # Calico (quay.io)
    "ei-docker-virtual/calico/node:v3.28.1"
    "ei-docker-virtual/calico/cni:v3.28.1"
    "ei-docker-virtual/calico/kube-controllers:v3.28.1"
    "ei-docker-virtual/calico/pod2daemon-flexvol:v3.28.1"
    # NRI plugins (ghcr.io)
    "ei-docker-virtual/containers/nri-plugins/nri-resource-policy-balloons:v0.12.2"
    "ei-docker-virtual/containers/nri-plugins/nri-config-manager:v0.12.2"
    # Misc (docker.io)
    "ei-docker-virtual/library/nginx:1.25.2-alpine"
    "ei-docker-virtual/library/registry:2"
    "ei-docker-virtual/ubuntu:22.04"
    "ei-docker-virtual/rancher/local-path-provisioner:v0.0.24"
    # Kubernetes Dashboard (docker.io)
    "ei-docker-virtual/kubernetesui/dashboard:v2.7.0"
    "ei-docker-virtual/kubernetesui/metrics-scraper:v1.0.8"
    # OpenVINO (docker.io)
    "ei-docker-virtual/openvino/model_server:latest"
  )

  local pulled=0 failed=0 fail_list=()
  for img in "${images[@]}"; do
    info "Pulling $jfrog/$img"
    if run docker pull "$jfrog/$img"; then
      ((pulled++))
    else
      warn "Failed to pull: $img"
      ((failed++))
      fail_list+=("$img")
    fi
  done

  # nginx: also pull by amd64 digest to force platform-specific manifest caching
  info "Pulling nginx by amd64 digest (forces platform-specific manifest cache)"
  run docker pull --platform linux/amd64 "$jfrog/ei-docker-virtual/library/nginx:1.25.2-alpine"
  run docker pull "$jfrog/ei-docker-virtual/library/nginx@sha256:fc2d39a0d6565db4bd6c94aa7b5efc2da67734cc97388afb5c72369a24bcfaea"

  # Manual push: busybox:1.28
  # Docker Hub v2 API drops manifests for very old tags - JFrog remote returns "manifest unknown"
  info "Pushing busybox:1.28 to ei-docker-local (old tag, JFrog remote can't proxy it)"
  if run docker pull "$jfrog/ei-docker-virtual/library/busybox:latest"; then
    run docker tag "$jfrog/ei-docker-virtual/library/busybox:latest" "$jfrog/ei-docker-local/library/busybox:1.28"
    run docker push "$jfrog/ei-docker-local/library/busybox:1.28"
  else
    warn "Could not pull busybox:latest through JFrog - skipping busybox:1.28 manual push"
  fi

  # Manual push: apisix-ingress-controller:1.8.0
  # Not cached in any JFrog remote - must pull directly from Docker Hub
  if [[ -n "$DOCKERHUB_USER" && -n "$DOCKERHUB_PASS" ]]; then
    info "Pushing apisix-ingress-controller:1.8.0 to ei-docker-local"
    run docker login -u "$DOCKERHUB_USER" -p "$DOCKERHUB_PASS" docker.io
    run docker pull docker.io/apache/apisix-ingress-controller:1.8.0
    run docker tag apache/apisix-ingress-controller:1.8.0 \
      "$jfrog/ei-docker-local/apache/apisix-ingress-controller:1.8.0"
    run docker push "$jfrog/ei-docker-local/apache/apisix-ingress-controller:1.8.0"
  else
    warn "Skipping apisix-ingress-controller:1.8.0 manual push - pass --dockerhub-user and --dockerhub-pass"
  fi

  success "3a complete: pulled=$pulled  failed=$failed"
  if [[ $failed -gt 0 ]]; then
    warn "Failed images:"
    for img in "${fail_list[@]}"; do warn "  $img"; done
  fi

  # Verify nginx is properly cached (requires Docker Accept headers)
  info "Verifying nginx manifest is accessible in JFrog..."
  local http_code
  http_code=$(curl -s -u "$JFROG_CREDS" \
    -H "Accept: application/vnd.docker.distribution.manifest.v2+json" \
    -H "Accept: application/vnd.docker.distribution.manifest.list.v2+json" \
    -o /dev/null -w "%{http_code}" \
    "${JFROG_URL%/artifactory}/v2/ei-docker-virtual/library/nginx/manifests/1.25.2-alpine")
  if [[ "$http_code" == "200" ]]; then
    success "nginx:1.25.2-alpine verified in JFrog (HTTP $http_code)"
  else
    warn "nginx manifest check returned HTTP $http_code (expected 200)"
  fi
}

# ---------------------------------------------------------------------------
# Step 3b - Helm Charts
# ---------------------------------------------------------------------------
step_3b() {
  step "3b - Helm Charts"
  local helmdir="$WORKDIR/helm-charts"
  mkdir -p "$helmdir"
  cd "$helmdir"

  # Add upstream helm repos
  run helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
  run helm repo add langfuse https://langfuse.github.io/langfuse-k8s
  run helm repo add apisix https://charts.apiseven.com
  run helm repo add nri-plugins https://containers.github.io/nri-plugins
  run helm repo update

  # Pull standard charts
  run helm pull ingress-nginx/ingress-nginx --version 4.12.2      --destination .
  run helm pull langfuse/langfuse           --version 1.5.1        --destination .
  run helm pull apisix/apisix               --version 2.8.1        --destination .
  run helm pull nri-plugins/nri-resource-policy-balloons --version v0.12.2 --destination .
  # NRI chart downloads as nri-resource-policy-balloons-helm-chart-v0.12.2.tgz (non-standard name)

  # Pull Bitnami OCI charts (from Docker Hub registry-1.docker.io/bitnamicharts)
  run helm pull oci://registry-1.docker.io/bitnamicharts/keycloak    --version 22.1.0 --destination .
  run helm pull oci://registry-1.docker.io/bitnamicharts/postgresql  --version 16.7.4 --destination .
  run helm pull oci://registry-1.docker.io/bitnamicharts/redis       --version 21.1.3 --destination .
  run helm pull oci://registry-1.docker.io/bitnamicharts/clickhouse  --version 8.0.5  --destination .
  run helm pull oci://registry-1.docker.io/bitnamicharts/minio       --version 14.10.5 --destination .
  run helm pull oci://registry-1.docker.io/bitnamicharts/valkey      --version 2.2.4  --destination .

  # Upload all tarballs to JFrog ei-helm-local via HTTP
  for chart in *.tgz; do
    [[ -f "$chart" ]] || continue
    jfrog_upload "$chart" "ei-helm-local/$chart"
  done

  # Generate and upload index.yaml (required - JFrog does not auto-generate it for HelmOCI repos)
  run helm repo index . --url "$JFROG_URL/ei-helm-local"
  jfrog_upload "index.yaml" "ei-helm-local/index.yaml"

  success "3b complete"
  cd - >/dev/null
}

# ---------------------------------------------------------------------------
# Step 3c - PyPI Packages
# ---------------------------------------------------------------------------
step_3c() {
  step "3c - PyPI Packages"
  local wheelsdir="$WORKDIR/wheels"
  mkdir -p "$wheelsdir"

  run pip3 download \
    ansible==9.8.0 ansible-core==2.16.18 \
    jinja2 jmespath==1.0.1 jsonschema==4.23.0 jsonschema-specifications \
    netaddr==1.3.0 kubernetes==35.0.0 pyyaml==6.0.3 \
    cryptography requests oauthlib requests-oauthlib urllib3 \
    certifi charset-normalizer idna packaging typing-extensions \
    six python-dateutil attrs rpds-py referencing resolvelib \
    durationpy websocket-client cffi pycparser markupsafe \
    -d "$wheelsdir"

  for pkg in "$wheelsdir"/*.whl "$wheelsdir"/*.tar.gz; do
    [[ -f "$pkg" ]] || continue
    jfrog_upload "$pkg" "ei-pypi-local/$(basename "$pkg")"
  done

  success "3c complete"
}

# ---------------------------------------------------------------------------
# Step 3d - pip Bootstrap Wheel
# ---------------------------------------------------------------------------
step_3d() {
  step "3d - pip Bootstrap Wheel"
  local pipdir="$WORKDIR/pip-dl"
  mkdir -p "$pipdir"

  run pip3 download pip --no-deps -d "$pipdir"

  local whl
  whl=$(ls "$pipdir"/pip-*.whl 2>/dev/null | head -1)
  if [[ -z "$whl" ]]; then
    error "pip wheel not found in $pipdir"
    return 1
  fi

  # Upload as generic name 'pip.whl' - deployment script reads version from WHEEL metadata
  jfrog_upload "$whl" "ei-generic-binaries/pip.whl"
  success "3d complete"
}

# ---------------------------------------------------------------------------
# Step 3e - Ansible Collections
# ---------------------------------------------------------------------------
step_3e() {
  step "3e - Ansible Collections"
  local colldir="$WORKDIR/ansible-collections"
  mkdir -p "$colldir"

  run ansible-galaxy collection download \
    kubernetes.core:6.3.0 \
    community.general:12.5.0 \
    ansible.posix \
    -p "$colldir"

  # Upload with -latest suffix - setup-env.sh looks for <namespace>-<name>-latest.tar.gz
  local kube_core_tgz  community_general_tgz  ansible_posix_tgz
  kube_core_tgz=$(ls "$colldir"/kubernetes-core-*.tar.gz 2>/dev/null | head -1)
  community_general_tgz=$(ls "$colldir"/community-general-*.tar.gz 2>/dev/null | head -1)
  ansible_posix_tgz=$(ls "$colldir"/ansible-posix-*.tar.gz 2>/dev/null | head -1)

  if [[ -n "$kube_core_tgz" ]]; then
    jfrog_upload "$kube_core_tgz" "ei-generic-binaries/ansible-collections/kubernetes-core-latest.tar.gz"
  else
    warn "kubernetes.core tarball not found - skipping"
  fi

  if [[ -n "$community_general_tgz" ]]; then
    jfrog_upload "$community_general_tgz" "ei-generic-binaries/ansible-collections/community-general-latest.tar.gz"
  else
    warn "community.general tarball not found - skipping"
  fi

  if [[ -n "$ansible_posix_tgz" ]]; then
    jfrog_upload "$ansible_posix_tgz" "ei-generic-binaries/ansible-collections/ansible-posix-latest.tar.gz"
  else
    warn "ansible.posix tarball not found - skipping"
  fi

  success "3e complete"
}

# ---------------------------------------------------------------------------
# Step 3f - apt .deb Files for jq
# ---------------------------------------------------------------------------
step_3f() {
  step "3f - apt .deb Files for jq"
  local debdir="$WORKDIR/apt-debs"
  mkdir -p "$debdir"
  cd "$debdir"

  # Download debs without installing them
  run apt-get download jq libjq1 libonig5

  for deb in *.deb; do
    [[ -f "$deb" ]] || continue
    jfrog_upload "$deb" "ei-generic-binaries/apt-debs/$deb"
  done

  success "3f complete"
  cd - >/dev/null
}

# ---------------------------------------------------------------------------
# Step 3g - Kubernetes Binaries
# ---------------------------------------------------------------------------
step_3g() {
  step "3g - Kubernetes Binaries (for Kubespray)"
  local bindir="$WORKDIR/k8s-binaries"
  mkdir -p "$bindir"
  cd "$bindir"

  # Kubernetes binaries (kubeadm, kubectl, kubelet)
  for bin in kubeadm kubectl kubelet; do
    run curl -fsSLO "https://dl.k8s.io/release/v1.30.4/bin/linux/amd64/$bin"
    jfrog_upload "$bin" "ei-generic-binaries/dl.k8s.io/release/v1.30.4/bin/linux/amd64/$bin"
  done

  # CNI plugins
  run curl -fsSLO "https://github.com/containernetworking/plugins/releases/download/v1.4.0/cni-plugins-linux-amd64-v1.4.0.tgz"
  jfrog_upload "cni-plugins-linux-amd64-v1.4.0.tgz" \
    "ei-generic-binaries/github.com/containernetworking/plugins/releases/download/v1.4.0/cni-plugins-linux-amd64-v1.4.0.tgz"

  # crictl
  run curl -fsSLO "https://github.com/kubernetes-sigs/cri-tools/releases/download/v1.30.0/crictl-v1.30.0-linux-amd64.tar.gz"
  jfrog_upload "crictl-v1.30.0-linux-amd64.tar.gz" \
    "ei-generic-binaries/github.com/kubernetes-sigs/cri-tools/releases/download/v1.30.0/crictl-v1.30.0-linux-amd64.tar.gz"

  # etcd
  run curl -fsSLO "https://github.com/etcd-io/etcd/releases/download/v3.5.12/etcd-v3.5.12-linux-amd64.tar.gz"
  jfrog_upload "etcd-v3.5.12-linux-amd64.tar.gz" \
    "ei-generic-binaries/github.com/etcd-io/etcd/releases/download/v3.5.12/etcd-v3.5.12-linux-amd64.tar.gz"

  # Calico binaries
  run curl -fsSLO "https://github.com/projectcalico/calico/releases/download/v3.28.1/calicoctl-linux-amd64"
  jfrog_upload "calicoctl-linux-amd64" \
    "ei-generic-binaries/github.com/projectcalico/calico/releases/download/v3.28.1/calicoctl-linux-amd64"

  run curl -fsSL -o "calico-v3.28.1.tar.gz" "https://github.com/projectcalico/calico/archive/v3.28.1.tar.gz"
  jfrog_upload "calico-v3.28.1.tar.gz" \
    "ei-generic-binaries/github.com/projectcalico/calico/archive/v3.28.1.tar.gz"

  # containerd
  run curl -fsSLO "https://github.com/containerd/containerd/releases/download/v1.7.21/containerd-1.7.21-linux-amd64.tar.gz"
  jfrog_upload "containerd-1.7.21-linux-amd64.tar.gz" \
    "ei-generic-binaries/github.com/containerd/containerd/releases/download/v1.7.21/containerd-1.7.21-linux-amd64.tar.gz"

  # runc
  run curl -fsSLO "https://github.com/opencontainers/runc/releases/download/v1.1.13/runc.amd64"
  jfrog_upload "runc.amd64" \
    "ei-generic-binaries/github.com/opencontainers/runc/releases/download/v1.1.13/runc.amd64"

  # helm tarball (used by inference-tools role in airgap install)
  run curl -fsSLO "https://get.helm.sh/helm-v3.15.4-linux-amd64.tar.gz"
  jfrog_upload "helm-v3.15.4-linux-amd64.tar.gz" \
    "ei-generic-binaries/get.helm.sh/helm-v3.15.4-linux-amd64.tar.gz"

  # get-pip.py (alternative pip bootstrap)
  run curl -fsSL -o "get-pip.py" "https://bootstrap.pypa.io/get-pip.py"
  jfrog_upload "get-pip.py" "ei-generic-binaries/get-pip.py"

  success "3g complete"
  cd - >/dev/null
}

# ---------------------------------------------------------------------------
# Step 3h - LLM Model Files
# ---------------------------------------------------------------------------
step_3h() {
  step "3h - LLM Model Files"

  if [[ -z "$HF_TOKEN" ]]; then
    warn "Skipping 3h: --hf-token not provided"
    warn "To upload LLM model files, re-run with: --step 3h --hf-token hf_..."
    return 0
  fi

  local modeldir="$WORKDIR/Llama-3.1-8B-Instruct"
  mkdir -p "$modeldir"

  info "Downloading meta-llama/Llama-3.1-8B-Instruct from HuggingFace..."
  run pip3 install -q huggingface_hub
  run python3 - <<PYEOF
from huggingface_hub import snapshot_download
snapshot_download(
    "meta-llama/Llama-3.1-8B-Instruct",
    local_dir="$modeldir",
    token="$HF_TOKEN"
)
PYEOF

  info "Uploading model files to JFrog ei-generic-models..."
  find "$modeldir" -type f | while read -r f; do
    rel="${f#$modeldir/}"
    jfrog_upload "$f" "ei-generic-models/Meta-Llama-3.1-8B-Instruct/$rel"
  done

  success "3h complete"
}

# ---------------------------------------------------------------------------
# Step 3i - Kubespray Tarball
# ---------------------------------------------------------------------------
step_3i() {
  step "3i - Kubespray Tarball"
  local kubedir="$WORKDIR/kubespray-build"
  mkdir -p "$kubedir"
  cd "$kubedir"

  if [[ ! -d "kubespray" ]]; then
    run git clone https://github.com/kubernetes-sigs/kubespray
  fi
  run git -C kubespray checkout v2.27.0

  run tar -czf kubespray.tar.gz kubespray/
  jfrog_upload "kubespray.tar.gz" "ei-generic-binaries/kubespray.tar.gz"

  success "3i complete"
  cd - >/dev/null
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
echo ""
echo "============================================================"
echo "  EI Airgap Asset Upload"
echo "  JFrog: $JFROG_URL"
echo "  Workdir: $WORKDIR"
echo "  Dry-run: $DRY_RUN"
echo "  Only step: ${ONLY_STEP:-all}"
echo "  Skip steps: ${SKIP_STEPS[*]:-none}"
echo "============================================================"
echo ""

if ! $DRY_RUN; then
  check_prereqs
  mkdir -p "$WORKDIR"
fi

should_run "3a" && step_3a
should_run "3b" && step_3b
should_run "3c" && step_3c
should_run "3d" && step_3d
should_run "3e" && step_3e
should_run "3f" && step_3f
should_run "3g" && step_3g
should_run "3h" && step_3h
should_run "3i" && step_3i

echo ""
success "All requested steps complete."
echo ""
echo "Next: Set all JFrog remote repos to Offline (Admin -> Repositories -> Edit each remote -> Advanced -> Offline)"
echo "      Then set airgap_enabled=on in core/inventory/inference-config.cfg on VM2 and run inference-stack-deploy.sh"
