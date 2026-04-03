#!/usr/bin/env bash
# Copyright (C) 2025-2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# Phase 0 – Step 2: Package all Helm chart external dependencies so they can be
# deployed without internet access.  Run on an INTERNET-CONNECTED machine.
#
# What this script does:
#   1. Adds / updates all required Helm repos.
#   2. Runs `helm dependency update` for each chart that has external deps.
#   3. Copies the vendor'd charts/ directory into airgap-bundle/helm/.
#   4. Packages each local Helm chart as a .tgz archive.
#
# Prerequisites: helm v3.14+, internet access, ~2 GB free disk space.
# Output:        airgap-bundle/helm/<chart-name>.tgz  and
#                core/helm-charts/<chart>/charts/ populated with sub-charts.
#
# Usage:
#   chmod +x 02-package-helm-deps.sh
#   ./02-package-helm-deps.sh [--output-dir <dir>]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
HELM_CHARTS_DIR="${REPO_ROOT}/core/helm-charts"
OUTPUT_DIR="${REPO_ROOT}/airgap-bundle/helm"

while [[ $# -gt 0 ]]; do
  case $1 in
    --output-dir) OUTPUT_DIR="$2"; shift 2 ;;
    *) shift ;;
  esac
done

echo "=== Enterprise Inference Airgap: Package Helm Dependencies ==="
echo "Helm charts dir : ${HELM_CHARTS_DIR}"
echo "Output dir      : ${OUTPUT_DIR}"
echo ""

mkdir -p "${OUTPUT_DIR}"

# ---------------------------------------------------------------------------
# 1. Add all required Helm repositories
# ---------------------------------------------------------------------------
declare -A HELM_REPOS=(
  ["bitnami"]="oci://registry-1.docker.io/bitnamicharts"
  ["apisix"]="https://charts.apiseven.com"
  ["grafana"]="https://grafana.github.io/helm-charts"
  ["open-telemetry"]="https://open-telemetry.github.io/opentelemetry-helm-charts"
  ["ingress-nginx"]="https://kubernetes.github.io/ingress-nginx"
  ["rook-release"]="https://charts.rook.io/release"
  ["keycloak"]="https://charts.bitnami.com/bitnami"
)

echo "[INFO] Adding Helm repositories..."
for repo_name in "${!HELM_REPOS[@]}"; do
  repo_url="${HELM_REPOS[$repo_name]}"
  # OCI repos don't use helm repo add
  if [[ "${repo_url}" == oci://* ]]; then
    echo "[SKIP] OCI repo ${repo_name} (${repo_url}) — pulled as chart dependency"
  else
    helm repo add "${repo_name}" "${repo_url}" --force-update || true
  fi
done
helm repo update
echo ""

# ---------------------------------------------------------------------------
# 2. Update dependencies for charts that have a Chart.yaml with dependencies
# ---------------------------------------------------------------------------
CHARTS_WITH_DEPS=(
  "genai-gateway"
  "genai-gateway-trace/charts/langfuse"
)

echo "[INFO] Updating Helm chart dependencies..."
for chart_rel in "${CHARTS_WITH_DEPS[@]}"; do
  chart_path="${HELM_CHARTS_DIR}/${chart_rel}"
  if [[ -f "${chart_path}/Chart.yaml" ]]; then
    echo "[DEP]  ${chart_rel}"
    helm dependency update "${chart_path}"
  else
    echo "[WARN] Chart not found: ${chart_path}" >&2
  fi
done
echo ""

# ---------------------------------------------------------------------------
# 3. Package each local chart into the output bundle directory
# ---------------------------------------------------------------------------
TOP_LEVEL_CHARTS=(
  "vllm"
  "tgi"
  "tei"
  "teirerank"
  "ovms"
  "genai-gateway"
  "genai-gateway-trace/charts/langfuse"
  "apisix-helm"
  "keycloak"
  "observability/logs-stack"
  "mcp-server-template"
  "ceph"
)

echo "[INFO] Packaging Helm charts..."
for chart_rel in "${TOP_LEVEL_CHARTS[@]}"; do
  chart_path="${HELM_CHARTS_DIR}/${chart_rel}"
  if [[ -f "${chart_path}/Chart.yaml" ]]; then
    chart_name=$(basename "${chart_rel}")
    echo "[PACK] ${chart_rel}"
    helm package "${chart_path}" --destination "${OUTPUT_DIR}"
  else
    echo "[WARN] Chart not found: ${chart_path}" >&2
  fi
done

echo ""
echo "=== Summary ==="
echo "Packaged charts saved to : ${OUTPUT_DIR}"
ls -lh "${OUTPUT_DIR}"/*.tgz 2>/dev/null || echo "No .tgz files found"
echo ""
echo "Next step: run 03-download-models.sh"
