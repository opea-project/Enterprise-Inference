#!/usr/bin/env bash
# One-shot script to build the patched sglang xeon image and import it
# into the k3s containerd cache so the chart can use it without a registry.
#
# Run with: sudo bash core/helm-charts/sglang/image-build/build-and-import.sh
set -euo pipefail

IMAGE_TAG="${IMAGE_TAG:-enterprise-inference/sglang:v0.5.12-xeon-fix11-debug}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "==> Ensuring docker is installed"
if ! command -v docker >/dev/null 2>&1; then
  apt-get update
  DEBIAN_FRONTEND=noninteractive apt-get install -y docker.io
  systemctl enable --now docker
fi
docker version --format 'Server: {{.Server.Version}}'

echo "==> Building $IMAGE_TAG"
cd "$SCRIPT_DIR"
docker build -t "$IMAGE_TAG" .

echo "==> Importing into k3s containerd"
# k3s ships its own containerd; piping a docker-save into k3s ctr image import
# makes the image directly available to k3s pods (no registry required).
docker save "$IMAGE_TAG" | k3s ctr images import -

echo "==> Verifying"
k3s ctr images ls -q | grep -F "$IMAGE_TAG" || {
  echo "Imported image not found in k3s containerd"
  exit 1
}

echo
echo "==> Done. Use in chart with:"
echo "    --set image.repository=${IMAGE_TAG%:*}"
echo "    --set image.tag=${IMAGE_TAG##*:}"
echo "    --set image.pullPolicy=Never"
