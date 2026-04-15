#!/usr/bin/env bash
# Copyright (C) 2025-2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# jfrog-create-repos.sh
#
# Creates all JFrog repositories required for EI airgapped deployment.
# Run this on any machine that can reach the JFrog instance.
#
# Usage:
#   ./jfrog-create-repos.sh [OPTIONS]
#
# Options:
#   --jfrog-url URL    JFrog base URL (default: http://100.67.177.217:8082/artifactory)
#   --jfrog-user USER  JFrog username (default: admin)
#   --jfrog-pass PASS  JFrog password (default: password)
#   -h, --help         Show this help

set -euo pipefail

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
JFROG_URL="http://100.67.177.217:8082/artifactory"
JFROG_USER="admin"
JFROG_PASS="password"

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------
while [[ $# -gt 0 ]]; do
  case $1 in
    --jfrog-url)  JFROG_URL="$2";  shift 2 ;;
    --jfrog-user) JFROG_USER="$2"; shift 2 ;;
    --jfrog-pass) JFROG_PASS="$2"; shift 2 ;;
    -h|--help)
      sed -n '/^# Usage:/,/^[^#]/p' "$0" | grep '^#' | sed 's/^# \?//'
      exit 0 ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

CREDS="${JFROG_USER}:${JFROG_PASS}"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
RED='\033[0;31m'; GREEN='\033[0;32m'; CYAN='\033[0;36m'; NC='\033[0m'
info()    { echo -e "${CYAN}[INFO]${NC}  $*"; }
success() { echo -e "${GREEN}[OK]${NC}    $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*" >&2; }

create_repo() {
  local name="$1" payload="$2"
  info "Creating $name ..."
  local http_code
  http_code=$(curl -su "$CREDS" -X PUT "$JFROG_URL/api/repositories/$name" \
    -H "Content-Type: application/json" \
    -d "$payload" \
    -o /tmp/jfrog_repo_resp.txt -w "%{http_code}")
  local resp
  resp=$(cat /tmp/jfrog_repo_resp.txt)
  if [[ "$http_code" == "200" || "$http_code" == "201" ]]; then
    success "$name created (HTTP $http_code)"
  elif echo "$resp" | grep -qi "already exists"; then
    success "$name already exists - skipping"
  else
    error "$name failed (HTTP $http_code): $resp"
  fi
}

# ---------------------------------------------------------------------------
# Pre-flight check
# ---------------------------------------------------------------------------
echo ""
echo "============================================================"
echo "  JFrog Repository Setup"
echo "  JFrog: $JFROG_URL"
echo "============================================================"
echo ""

info "Checking JFrog connectivity..."
if ! curl -su "$CREDS" "$JFROG_URL/api/system/ping" | grep -q "OK"; then
  error "Cannot reach JFrog at $JFROG_URL — check URL, credentials and that Artifactory is running"
  exit 1
fi
success "JFrog reachable"
echo ""

# ---------------------------------------------------------------------------
# Docker repositories
# ---------------------------------------------------------------------------
echo "── Docker Repositories ──────────────────────────────────────"

create_repo "ei-docker-local" \
  '{"rclass":"local","packageType":"docker"}'

create_repo "ei-docker-dockerhub" \
  '{"rclass":"remote","packageType":"docker","url":"https://registry-1.docker.io"}'

create_repo "ei-docker-ecr" \
  '{"rclass":"remote","packageType":"docker","url":"https://public.ecr.aws"}'

create_repo "ei-docker-ghcr" \
  '{"rclass":"remote","packageType":"docker","url":"https://ghcr.io"}'

create_repo "ei-docker-k8s" \
  '{"rclass":"remote","packageType":"docker","url":"https://registry.k8s.io"}'

create_repo "ei-docker-quay" \
  '{"rclass":"remote","packageType":"docker","url":"https://quay.io"}'

create_repo "ei-docker-virtual" \
  '{"rclass":"virtual","packageType":"docker","repositories":["ei-docker-local","ei-docker-dockerhub","ei-docker-ecr","ei-docker-ghcr","ei-docker-k8s","ei-docker-quay"]}'

echo ""

# ---------------------------------------------------------------------------
# Helm repositories
# ---------------------------------------------------------------------------
echo "── Helm Repositories ────────────────────────────────────────"

create_repo "ei-helm-local" \
  '{"rclass":"local","packageType":"helmoci"}'

create_repo "ei-helm-virtual" \
  '{"rclass":"virtual","packageType":"helmoci","repositories":["ei-helm-local"]}'

echo ""

# ---------------------------------------------------------------------------
# PyPI repositories
# ---------------------------------------------------------------------------
echo "── PyPI Repositories ────────────────────────────────────────"

create_repo "ei-pypi-local" \
  '{"rclass":"local","packageType":"pypi"}'

create_repo "ei-pypi-remote" \
  '{"rclass":"remote","packageType":"pypi","url":"https://pypi.org"}'

create_repo "ei-pypi-virtual" \
  '{"rclass":"virtual","packageType":"pypi","repositories":["ei-pypi-local","ei-pypi-remote"]}'

echo ""

# ---------------------------------------------------------------------------
# Debian repositories
# ---------------------------------------------------------------------------
echo "── Debian Repositories ──────────────────────────────────────"

create_repo "ei-debian-ubuntu" \
  '{"rclass":"remote","packageType":"debian","url":"http://archive.ubuntu.com/ubuntu"}'

create_repo "ei-debian-virtual" \
  '{"rclass":"virtual","packageType":"debian","repositories":["ei-debian-ubuntu"]}'

echo ""

# ---------------------------------------------------------------------------
# Generic repositories
# ---------------------------------------------------------------------------
echo "── Generic Repositories ─────────────────────────────────────"

create_repo "ei-generic-binaries" \
  '{"rclass":"local","packageType":"generic"}'

create_repo "ei-generic-models" \
  '{"rclass":"local","packageType":"generic"}'

echo ""

# ---------------------------------------------------------------------------
# Verify all repos
# ---------------------------------------------------------------------------
echo "── Verification ─────────────────────────────────────────────"
info "Listing all created repositories..."
curl -su "$CREDS" "$JFROG_URL/api/repositories" | \
  python3 -c "import sys,json; [print('  -', r['key']) for r in json.load(sys.stdin)]"

echo ""
success "All repositories created successfully."
echo ""
echo "Next steps:"
echo "  1. Enable anonymous read access: Admin -> Security -> Settings -> Allow Anonymous Access"
echo "  2. Run jfrog-upload-all-assets.sh to pre-load all Docker images, Helm charts, binaries"
