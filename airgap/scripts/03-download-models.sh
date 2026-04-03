#!/usr/bin/env bash
# Copyright (C) 2025-2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# Phase 0 – Step 3: Pre-download AI/ML models from HuggingFace Hub.
# Run on an INTERNET-CONNECTED machine.
#
# Models are saved as a flat directory tree under airgap-bundle/models/<model-id>/.
# In the airgapped environment the directory is mounted as a hostPath or PVC so
# inference pods can load models from disk without network access.
#
# Prerequisites:
#   - Python 3.8+ with huggingface_hub installed  (pip install huggingface_hub)
#   - HuggingFace token in env var HF_TOKEN (required for gated models)
#   - 500 GB+ free disk space (model sizes vary; 7B models ~14 GB each)
#
# Usage:
#   export HF_TOKEN=hf_xxxxx
#   chmod +x 03-download-models.sh
#   ./03-download-models.sh [--output-dir <dir>] [--models "model1 model2"]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
OUTPUT_DIR="${REPO_ROOT}/airgap-bundle/models"

# Default model list — matches inference-config.cfg defaults and common deployments.
# Override with --models flag or MODEL_LIST env var.
DEFAULT_MODELS=(
  "Intel/neural-chat-7b-v3-3"
  "meta-llama/Llama-3.2-3B-Instruct"
  "mistralai/Mistral-7B-Instruct-v0.3"
  "BAAI/bge-base-en-v1.5"
  "BAAI/bge-reranker-base"
)

MODEL_LIST=("${DEFAULT_MODELS[@]}")

while [[ $# -gt 0 ]]; do
  case $1 in
    --output-dir) OUTPUT_DIR="$2"; shift 2 ;;
    --models)     IFS=' ' read -r -a MODEL_LIST <<< "$2"; shift 2 ;;
    *) shift ;;
  esac
done

echo "=== Enterprise Inference Airgap: Download HuggingFace Models ==="
echo "Output dir : ${OUTPUT_DIR}"
echo "Models     : ${MODEL_LIST[*]}"
echo ""

if [[ -z "${HF_TOKEN:-}" ]]; then
  echo "[WARN] HF_TOKEN not set. Gated/private models will fail to download."
fi

mkdir -p "${OUTPUT_DIR}"

# Verify huggingface_hub is available
if ! python3 -c "import huggingface_hub" 2>/dev/null; then
  echo "[INFO] Installing huggingface_hub..."
  pip3 install --quiet huggingface_hub
fi

FAILED_MODELS=()

for MODEL_ID in "${MODEL_LIST[@]}"; do
  MODEL_DIR="${OUTPUT_DIR}/${MODEL_ID}"
  if [[ -d "${MODEL_DIR}" ]]; then
    echo "[SKIP] ${MODEL_ID}  (already downloaded)"
    continue
  fi

  echo "[DOWNLOAD] ${MODEL_ID}..."
  mkdir -p "${MODEL_DIR}"

  if python3 - <<PYEOF
import sys
from huggingface_hub import snapshot_download
import os

token = os.environ.get("HF_TOKEN")
try:
    snapshot_download(
        repo_id="${MODEL_ID}",
        local_dir="${MODEL_DIR}",
        token=token,
        ignore_patterns=["*.msgpack", "flax_model*", "tf_model*", "rust_model*"],
    )
    print(f"[OK] Downloaded ${MODEL_ID}")
except Exception as e:
    print(f"[ERROR] ${MODEL_ID}: {e}", file=sys.stderr)
    sys.exit(1)
PYEOF
  then
    echo "[OK]  ${MODEL_ID}"
  else
    echo "[ERROR] Failed to download ${MODEL_ID}" >&2
    FAILED_MODELS+=("${MODEL_ID}")
    rm -rf "${MODEL_DIR}"
  fi
done

echo ""
echo "=== Summary ==="
echo "Models saved to : ${OUTPUT_DIR}"
du -sh "${OUTPUT_DIR}"/* 2>/dev/null | sort -h || true

if [[ ${#FAILED_MODELS[@]} -gt 0 ]]; then
  echo ""
  echo "FAILED models (${#FAILED_MODELS[@]}):"
  for m in "${FAILED_MODELS[@]}"; do
    echo "  - ${m}"
  done
  exit 1
fi

echo ""
echo "Next step: run 04-download-tools.sh"
