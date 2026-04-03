#!/usr/bin/env bash
# Copyright (C) 2025-2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# Phase 0 – Step 1: Pull all container images and save them as compressed tarballs.
# Run this script on an INTERNET-CONNECTED machine BEFORE transferring the bundle
# to the airgapped environment.
#
# Prerequisites: docker (or podman) CLI, ~150 GB free disk space.
# Output:        airgap-bundle/images/<image-name>.tar.gz per image.
#
# Usage:
#   chmod +x 01-pull-save-images.sh
#   ./01-pull-save-images.sh [--output-dir <dir>]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
IMAGE_LIST="${SCRIPT_DIR}/../image-list.txt"
OUTPUT_DIR="${1:-${REPO_ROOT}/airgap-bundle/images}"

# Allow override via flag
while [[ $# -gt 0 ]]; do
  case $1 in
    --output-dir) OUTPUT_DIR="$2"; shift 2 ;;
    *) shift ;;
  esac
done

CONTAINER_CLI="docker"
if ! command -v docker &>/dev/null && command -v podman &>/dev/null; then
  CONTAINER_CLI="podman"
fi

echo "=== Enterprise Inference Airgap: Pull & Save Images ==="
echo "Container CLI : ${CONTAINER_CLI}"
echo "Image list    : ${IMAGE_LIST}"
echo "Output dir    : ${OUTPUT_DIR}"
echo ""

mkdir -p "${OUTPUT_DIR}"

FAILED_IMAGES=()

while IFS= read -r line; do
  # Skip blank lines and comments
  [[ -z "${line}" || "${line}" == \#* ]] && continue

  IMAGE="${line}"
  # Create a filesystem-safe filename: replace / : with _
  SAFE_NAME="${IMAGE//\//_}"
  SAFE_NAME="${SAFE_NAME//:/_}"
  TARBALL="${OUTPUT_DIR}/${SAFE_NAME}.tar.gz"

  if [[ -f "${TARBALL}" ]]; then
    echo "[SKIP]  ${IMAGE}  (already saved)"
    continue
  fi

  echo "[PULL]  ${IMAGE}"
  if ! ${CONTAINER_CLI} pull "${IMAGE}"; then
    echo "[ERROR] Failed to pull ${IMAGE}" >&2
    FAILED_IMAGES+=("${IMAGE}")
    continue
  fi

  echo "[SAVE]  ${IMAGE} -> ${TARBALL}"
  if ! ${CONTAINER_CLI} save "${IMAGE}" | gzip -9 > "${TARBALL}"; then
    echo "[ERROR] Failed to save ${IMAGE}" >&2
    FAILED_IMAGES+=("${IMAGE}")
    rm -f "${TARBALL}"
    continue
  fi

  echo "[OK]    ${IMAGE}"
done < "${IMAGE_LIST}"

echo ""
echo "=== Summary ==="
TOTAL=$(grep -c '^[^#]' "${IMAGE_LIST}" || true)
echo "Total images  : ${TOTAL}"
echo "Saved to      : ${OUTPUT_DIR}"

if [[ ${#FAILED_IMAGES[@]} -gt 0 ]]; then
  echo ""
  echo "FAILED images (${#FAILED_IMAGES[@]}):"
  for img in "${FAILED_IMAGES[@]}"; do
    echo "  - ${img}"
  done
  exit 1
fi

echo ""
echo "All images saved successfully. Next step: run 02-package-helm-deps.sh"
