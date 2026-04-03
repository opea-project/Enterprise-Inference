#!/usr/bin/env bash
# Copyright (C) 2025-2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# Phase 0 – Step 5: Create a single transfer archive (bundle) from all airgap
# artifacts produced by steps 01–04.  Run on an INTERNET-CONNECTED machine.
#
# The resulting bundle is a single .tar.gz (or split into 4 GB chunks for USB
# transfer via --split flag) that can be physically moved to the airgapped site.
#
# Prerequisites: Steps 01–04 have been executed successfully.
# Output:        enterprise-inference-airgap-bundle-<date>.tar.gz (or .tar.gz.*)
#
# Usage:
#   chmod +x 05-bundle-package.sh
#   ./05-bundle-package.sh [--split] [--output-dir <dir>]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
BUNDLE_SRC="${REPO_ROOT}/airgap-bundle"
OUTPUT_DIR="${REPO_ROOT}"
SPLIT=false
DATE=$(date +%Y%m%d)
BUNDLE_NAME="enterprise-inference-airgap-bundle-${DATE}"

while [[ $# -gt 0 ]]; do
  case $1 in
    --split)      SPLIT=true; shift ;;
    --output-dir) OUTPUT_DIR="$2"; shift 2 ;;
    *) shift ;;
  esac
done

BUNDLE_ARCHIVE="${OUTPUT_DIR}/${BUNDLE_NAME}.tar.gz"

echo "=== Enterprise Inference Airgap: Create Transfer Bundle ==="
echo "Source dir     : ${BUNDLE_SRC}"
echo "Output archive : ${BUNDLE_ARCHIVE}"
echo "Split into 4GB : ${SPLIT}"
echo ""

# Verify all expected sub-dirs are present
for sub in images helm models tools; do
  if [[ ! -d "${BUNDLE_SRC}/${sub}" ]]; then
    echo "[ERROR] Missing sub-directory: ${BUNDLE_SRC}/${sub}" >&2
    echo "        Run steps 01–04 first." >&2
    exit 1
  fi
done

# Also bundle the airgap/ directory from the repo (configs, manifests, playbooks, etc.)
echo "[INFO] Adding airgap config files to bundle..."
AIRGAP_DIR="${REPO_ROOT}/airgap"

echo "[INFO] Creating archive (this may take a while)..."
tar -czf "${BUNDLE_ARCHIVE}" \
  -C "${REPO_ROOT}" \
  airgap-bundle/ \
  airgap/

echo "[OK]  Archive created: ${BUNDLE_ARCHIVE}"
du -sh "${BUNDLE_ARCHIVE}"

if [[ "${SPLIT}" == true ]]; then
  echo "[INFO] Splitting into 4 GB chunks..."
  split -b 4G "${BUNDLE_ARCHIVE}" "${BUNDLE_ARCHIVE}."
  rm -f "${BUNDLE_ARCHIVE}"
  echo "[OK]  Split files:"
  ls -lh "${BUNDLE_ARCHIVE}."* 2>/dev/null || true
fi

# Generate SHA-256 checksum for integrity verification
echo "[INFO] Generating checksum..."
if [[ "${SPLIT}" == true ]]; then
  sha256sum "${BUNDLE_ARCHIVE}."* > "${OUTPUT_DIR}/${BUNDLE_NAME}.sha256"
else
  sha256sum "${BUNDLE_ARCHIVE}" > "${OUTPUT_DIR}/${BUNDLE_NAME}.sha256"
fi
cat "${OUTPUT_DIR}/${BUNDLE_NAME}.sha256"

echo ""
echo "=== Transfer Instructions ==="
echo "1. Copy the archive (and .sha256 file) to the airgapped environment via"
echo "   secure media (USB, SCP to bastion, etc.)."
echo ""
echo "2. On the airgapped machine, verify integrity:"
echo "   sha256sum -c ${BUNDLE_NAME}.sha256"
echo ""
echo "3. Extract the bundle:"
if [[ "${SPLIT}" == true ]]; then
  echo "   cat ${BUNDLE_NAME}.tar.gz.* | tar -xz"
else
  echo "   tar -xzf ${BUNDLE_NAME}.tar.gz"
fi
echo ""
echo "4. Follow the airgapped deployment guide:"
echo "   airgap/docs/airgap-deployment-guide.md"
echo ""
echo "Next step (on airgapped machine): run airgap/scripts/06-setup-private-registry.sh"
