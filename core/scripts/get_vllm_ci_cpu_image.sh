#!/usr/bin/env bash
set -euo pipefail

# Config
OWNER="vllm-project"
REPO="vllm"
ECR_ALIAS="q9t5s3a7"
CI_REPO="vllm-ci-test-repo"

GITHUB_API="https://api.github.com"

# Optional: set GITHUB_TOKEN to avoid rate limits
AUTH_HEADER=()
if [[ -n "${GITHUB_TOKEN:-}" ]]; then
  AUTH_HEADER=(-H "Authorization: Bearer ${GITHUB_TOKEN}")
fi

# If user passes a tag (e.g. v0.11.2 or 0.11.2), use it.
# Otherwise, grab the latest tag from GitHub.
RAW_TAG="${1:-}"

if [[ -z "$RAW_TAG" ]]; then
  echo "==> Fetching latest tag from GitHub..."
  RAW_TAG=$(curl -sS "${AUTH_HEADER[@]}" \
    "${GITHUB_API}/repos/${OWNER}/${REPO}/tags?per_page=1" \
    | jq -r '.[0].name')

  if [[ "$RAW_TAG" == "null" || -z "$RAW_TAG" ]]; then
    echo "ERROR: Could not determine latest tag from GitHub" >&2
    exit 1
  fi
fi

# Normalize tag: if it doesn't start with "v", add it (so 0.11.2 -> v0.11.2)
if [[ "$RAW_TAG" =~ ^v ]]; then
  TAG="$RAW_TAG"
else
  TAG="v${RAW_TAG}"
fi

echo "Using tag: ${TAG}"

# Get the full commit SHA for this tag
echo "==> Resolving tag to commit SHA..."
FULL_SHA=$(curl -sS "${AUTH_HEADER[@]}" \
  "${GITHUB_API}/repos/${OWNER}/${REPO}/commits/${TAG}" \
  | jq -r '.sha')

if [[ -z "$FULL_SHA" || "$FULL_SHA" == "null" ]]; then
  echo "ERROR: Could not resolve tag '${TAG}' to a commit SHA" >&2
  exit 1
fi

echo "Full SHA: ${FULL_SHA}"

CPU_TAG="${FULL_SHA}-cpu"
IMAGE_URL="public.ecr.aws/${ECR_ALIAS}/${CI_REPO}:${CPU_TAG}"

echo
echo "✅ vLLM CI CPU image for ${TAG}:"
echo "${IMAGE_URL}"

# Optional: sanity check if docker is available
if command -v docker >/dev/null 2>&1; then
  echo
  echo "==> Optional: checking if image is pullable with docker manifest inspect..."
  if docker manifest inspect "${IMAGE_URL}" >/dev/null 2>&1; then
    echo "Image exists and is pullable."
  else
    echo "WARNING: docker could not inspect the image (it may still be fine; could be network/registry issue)."
  fi
fi

