#!/usr/bin/env bash
# Copyright (C) 2025-2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# Phase 0 – Step 4: Download all CLI binaries needed by the bastion node so
# that setup-bastion.yml can install them offline.
# Run on an INTERNET-CONNECTED machine.
#
# Downloads:
#   - kubectl  v1.29.0
#   - helm     v3.14.0
#   - yq       v4.40.5
#   - ansible  (pip wheel bundle)
#   - Python packages: kubernetes, pyyaml, jsonpatch, requests, urllib3
#
# Output: airgap-bundle/tools/
#
# Usage:
#   chmod +x 04-download-tools.sh
#   ./04-download-tools.sh [--output-dir <dir>]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
OUTPUT_DIR="${REPO_ROOT}/airgap-bundle/tools"
ARCH="amd64"
OS="linux"

KUBECTL_VERSION="v1.29.0"
HELM_VERSION="v3.14.0"
YQ_VERSION="v4.40.5"

while [[ $# -gt 0 ]]; do
  case $1 in
    --output-dir) OUTPUT_DIR="$2"; shift 2 ;;
    --arch)       ARCH="$2"; shift 2 ;;
    *) shift ;;
  esac
done

echo "=== Enterprise Inference Airgap: Download CLI Tools ==="
echo "Output dir : ${OUTPUT_DIR}"
echo "OS/Arch    : ${OS}/${ARCH}"
echo ""

mkdir -p "${OUTPUT_DIR}/pip-packages"

# Helper: download only if not already present
download_if_missing() {
  local url="$1"
  local dest="$2"
  if [[ -f "${dest}" ]]; then
    echo "[SKIP] $(basename "${dest}")  (already downloaded)"
    return
  fi
  echo "[GET]  ${url}"
  curl -fsSL --retry 3 -o "${dest}" "${url}"
  echo "[OK]   $(basename "${dest}")"
}

# ---------------------------------------------------------------------------
# kubectl
# ---------------------------------------------------------------------------
echo "--- kubectl ${KUBECTL_VERSION} ---"
download_if_missing \
  "https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/${OS}/${ARCH}/kubectl" \
  "${OUTPUT_DIR}/kubectl"
chmod +x "${OUTPUT_DIR}/kubectl"

# ---------------------------------------------------------------------------
# helm
# ---------------------------------------------------------------------------
echo "--- helm ${HELM_VERSION} ---"
HELM_TARBALL="helm-${HELM_VERSION}-${OS}-${ARCH}.tar.gz"
download_if_missing \
  "https://get.helm.sh/${HELM_TARBALL}" \
  "${OUTPUT_DIR}/${HELM_TARBALL}"
# Extract the binary
if [[ ! -f "${OUTPUT_DIR}/helm" ]]; then
  tar -xzf "${OUTPUT_DIR}/${HELM_TARBALL}" -C "${OUTPUT_DIR}" "${OS}-${ARCH}/helm" \
    --strip-components=1
fi
chmod +x "${OUTPUT_DIR}/helm"

# ---------------------------------------------------------------------------
# yq
# ---------------------------------------------------------------------------
echo "--- yq ${YQ_VERSION} ---"
download_if_missing \
  "https://github.com/mikefarah/yq/releases/download/${YQ_VERSION}/yq_${OS}_${ARCH}" \
  "${OUTPUT_DIR}/yq"
chmod +x "${OUTPUT_DIR}/yq"

# ---------------------------------------------------------------------------
# Python pip wheel bundle (ansible + Kubernetes client)
# ---------------------------------------------------------------------------
echo "--- Python pip packages ---"
PIP_PACKAGES=(
  ansible
  kubernetes
  pyyaml
  jsonpatch
  requests
  urllib3
  huggingface_hub
)
PIP_BUNDLE_DIR="${OUTPUT_DIR}/pip-packages"

if [[ "$(ls -A "${PIP_BUNDLE_DIR}" 2>/dev/null | wc -l)" -gt 0 ]]; then
  echo "[SKIP] pip wheel bundle already present in ${PIP_BUNDLE_DIR}"
else
  echo "[DOWNLOAD] pip wheels for: ${PIP_PACKAGES[*]}"
  pip3 download \
    --dest "${PIP_BUNDLE_DIR}" \
    --no-deps \
    "${PIP_PACKAGES[@]}"
  # Also include transitive deps
  pip3 download \
    --dest "${PIP_BUNDLE_DIR}" \
    "${PIP_PACKAGES[@]}"
fi

echo ""
echo "=== Summary ==="
echo "Tools saved to : ${OUTPUT_DIR}"
ls -lh "${OUTPUT_DIR}"/{kubectl,helm,yq} 2>/dev/null || true
echo "pip wheels     : $(ls "${PIP_BUNDLE_DIR}" | wc -l) files"
echo ""
echo "Next step: run 05-bundle-package.sh"
