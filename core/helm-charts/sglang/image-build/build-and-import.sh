#!/usr/bin/env bash
# One-shot script to build the patched sglang xeon image and load it
# into the local containerd image store, so the chart can use it without
# pushing to an external registry.
#
# Auto-detects the runtime:
#   - OPEA / kubeadm-based clusters: containerd accessed via `nerdctl`
#     under the `k8s.io` namespace (where kubelet pulls from). Built
#     directly there; no separate import step.
#   - k3s clusters: `docker build` then `docker save | k3s ctr images
#     import -`. Installs docker.io if missing.
#
# Run with: sudo bash core/helm-charts/sglang/image-build/build-and-import.sh
set -euo pipefail

IMAGE_TAG="${IMAGE_TAG:-enterprise-inference/sglang:v0.5.12-xeon-fix11-debug}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

cd "$SCRIPT_DIR"

if command -v nerdctl >/dev/null 2>&1 && command -v containerd >/dev/null 2>&1; then
  RUNTIME=nerdctl
elif command -v k3s >/dev/null 2>&1; then
  RUNTIME=k3s
else
  echo "ERROR: neither nerdctl (kubeadm/containerd) nor k3s detected." >&2
  echo "Install one of them, or build manually and push to a registry." >&2
  exit 1
fi

echo "==> Detected container runtime: $RUNTIME"

case "$RUNTIME" in
  nerdctl)
    # nerdctl needs buildkitd to run `nerdctl build`. buildkit isn't in
    # Ubuntu apt — install from upstream GitHub releases (~30 MB).
    if ! command -v buildctl >/dev/null 2>&1; then
      BUILDKIT_VERSION="${BUILDKIT_VERSION:-v0.18.1}"
      echo "==> Installing buildkit ${BUILDKIT_VERSION} from GitHub releases"
      tmpdir=$(mktemp -d)
      curl -fsSL \
        "https://github.com/moby/buildkit/releases/download/${BUILDKIT_VERSION}/buildkit-${BUILDKIT_VERSION}.linux-amd64.tar.gz" \
        | tar -xz -C "$tmpdir"
      install -m 0755 "$tmpdir/bin/buildctl"  /usr/local/bin/buildctl
      install -m 0755 "$tmpdir/bin/buildkitd" /usr/local/bin/buildkitd
      rm -rf "$tmpdir"
    fi
    if ! pgrep -x buildkitd >/dev/null 2>&1; then
      echo "==> Starting buildkitd in the background"
      mkdir -p /run/buildkit
      nohup /usr/local/bin/buildkitd >/var/log/buildkitd.log 2>&1 &
      for i in 1 2 3 4 5 6 7 8 9 10; do
        [ -S /run/buildkit/buildkitd.sock ] && break
        sleep 1
      done
      [ -S /run/buildkit/buildkitd.sock ] || {
        echo "buildkitd did not come up; see /var/log/buildkitd.log" >&2
        exit 1
      }
    fi

    # nerdctl builds directly into containerd's image store. Pin namespace
    # to k8s.io so kubelet can find the image without a separate import.
    echo "==> Building $IMAGE_TAG via nerdctl (namespace k8s.io)"
    nerdctl --namespace k8s.io build -t "$IMAGE_TAG" .

    echo "==> Verifying"
    nerdctl --namespace k8s.io images "$IMAGE_TAG" --format '{{.Repository}}:{{.Tag}}' \
      | grep -F "$IMAGE_TAG" || {
        echo "Image not found in containerd k8s.io namespace" >&2
        exit 1
      }
    ;;

  k3s)
    echo "==> Ensuring docker is installed"
    if ! command -v docker >/dev/null 2>&1; then
      apt-get update
      DEBIAN_FRONTEND=noninteractive apt-get install -y docker.io
      systemctl enable --now docker
    fi
    docker version --format 'Server: {{.Server.Version}}'

    echo "==> Building $IMAGE_TAG via docker"
    docker build -t "$IMAGE_TAG" .

    echo "==> Importing into k3s containerd"
    docker save "$IMAGE_TAG" | k3s ctr images import -

    echo "==> Verifying"
    k3s ctr images ls -q | grep -F "$IMAGE_TAG" || {
      echo "Imported image not found in k3s containerd" >&2
      exit 1
    }
    ;;
esac

echo
echo "==> Done. Image $IMAGE_TAG is loaded in the local containerd image store."
echo "==> The chart's values.yaml already defaults to this tag with"
echo "    pullPolicy: IfNotPresent. No further overrides required."
