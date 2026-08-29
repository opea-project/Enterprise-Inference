#!/usr/bin/env bash
# One-shot bootstrap for testing the sglang Helm chart on a single Xeon box.
# Installs: k3s (single-node), helm, kubectl symlink. Sets up kubeconfig for $USER.
# Run with: sudo bash scripts/bootstrap-k3s.sh
set -euo pipefail

REAL_USER="${SUDO_USER:-$USER}"
REAL_HOME="$(getent passwd "$REAL_USER" | cut -d: -f6)"

echo "==> Installing k3s (single-node, embedded containerd, embedded etcd)..."
# --write-kubeconfig-mode 644 so non-root can read it
# --disable traefik because we don't need an ingress for the smoke test
curl -sfL https://get.k3s.io | \
  INSTALL_K3S_EXEC="--write-kubeconfig-mode 644 --disable traefik" \
  sh -

echo "==> Waiting for k3s API to be ready..."
for i in $(seq 1 60); do
  if k3s kubectl get nodes >/dev/null 2>&1; then break; fi
  sleep 2
done
k3s kubectl get nodes -o wide

echo "==> Setting up kubectl + kubeconfig for $REAL_USER..."
ln -sf /usr/local/bin/k3s /usr/local/bin/kubectl
install -d -o "$REAL_USER" -g "$REAL_USER" "$REAL_HOME/.kube"
install -m 600 -o "$REAL_USER" -g "$REAL_USER" /etc/rancher/k3s/k3s.yaml "$REAL_HOME/.kube/config"

echo "==> Installing helm..."
curl -sfL https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash

echo "==> Versions:"
kubectl version --client=true 2>&1 | head -3
helm version --short
echo
echo "==> Bootstrap complete. As $REAL_USER, you can now run:"
echo "    kubectl get nodes"
echo "    helm lint core/helm-charts/sglang"
