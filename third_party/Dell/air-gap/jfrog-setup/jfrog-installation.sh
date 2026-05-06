#!/usr/bin/env bash
# Copyright (C) 2025-2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# jfrog-installation.sh
#
# Step 1 of 2 for EI airgap VM1 setup.
# Installs all required tools and JFrog Artifactory on VM1.
#
# After this script completes:
#   1. Open http://<VM1-IP>:8082 in a browser
#      (SSH tunnel: ssh -L 8082:localhost:8082 user@<VM1-IP> -N  then open http://localhost:8082)
#   2. Log in with admin / password
#   3. Activate license: Admin → Artifactory License → paste trial key → Save
#   4. Run jfrog-setup.sh to create repos and upload all EI assets
#
# Usage:
#   sudo ./jfrog-installation.sh [OPTIONS]
#
# Options:
#   --jfrog-port PORT   JFrog HTTP port (default: 8082)
#   --skip-jfrog        Install tools only, skip JFrog installation
#   -h, --help          Show this help message

set -euo pipefail

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
JFROG_PORT="${JFROG_PORT:-8082}"
SKIP_JFROG=false

# ---------------------------------------------------------------------------
# Colours
# ---------------------------------------------------------------------------
RED='\033[0;31m'; YELLOW='\033[1;33m'; GREEN='\033[0;32m'; CYAN='\033[0;36m'; NC='\033[0m'
info()    { echo -e "${CYAN}[INFO]${NC}  $*"; }
success() { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*" >&2; }
section() {
  echo ""
  echo -e "${CYAN}══════════════════════════════════════════${NC}"
  echo -e "${CYAN}  $*${NC}"
  echo -e "${CYAN}══════════════════════════════════════════${NC}"
}

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------
while [[ $# -gt 0 ]]; do
  case $1 in
    --jfrog-port) JFROG_PORT="$2"; shift 2 ;;
    --skip-jfrog) SKIP_JFROG=true; shift ;;
    -h|--help)
      sed -n '/^# Usage:/,/^[^#]/p' "$0" | grep '^#' | sed 's/^# \?//'
      exit 0 ;;
    *) error "Unknown option: $1"; exit 1 ;;
  esac
done

if [[ "$EUID" -ne 0 ]]; then
  error "This script must be run as root: sudo $0 $*"
  exit 1
fi

echo ""
echo "============================================================"
echo "  VM1 Setup — Prerequisites + JFrog Artifactory"
echo "  JFrog port:       $JFROG_PORT"
echo "  Skip JFrog:       $SKIP_JFROG"
echo "============================================================"

# ---------------------------------------------------------------------------
# Step 1 — Install prerequisites
# ---------------------------------------------------------------------------
section "Step 1 — Install Prerequisites"

info "Updating package lists..."
apt-get update -qq

info "Installing required packages..."
apt-get install -y \
  curl \
  wget \
  git \
  jq \
  skopeo \
  net-tools \
  ca-certificates \
  gnupg \
  lsb-release \
  unzip \
  tar \
  vim \
  software-properties-common \
  python3 \
  python3-pip \
  ansible \
  db5.3-util

info "Verifying installed tools..."
for cmd in curl wget git jq skopeo python3 pip3 ansible ansible-galaxy; do
  if command -v "$cmd" &>/dev/null; then
    success "$cmd found: $(command -v $cmd)"
  else
    warn "$cmd not found after install"
  fi
done

# ---------------------------------------------------------------------------
# Step 2 — Install Helm
# ---------------------------------------------------------------------------
section "Step 2 — Install Helm"

if command -v helm &>/dev/null; then
  success "helm already installed: $(helm version --short 2>/dev/null)"
else
  info "Installing helm via official script..."
  curl -fsSL https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
  success "helm installed: $(helm version --short)"
fi

# ---------------------------------------------------------------------------
# Step 3 — Fix system limits for JFrog
# ---------------------------------------------------------------------------
section "Step 3 — Fix System Limits"

info "Setting fs.inotify.max_user_instances=512..."
sysctl -w fs.inotify.max_user_instances=512

if grep -q "fs.inotify.max_user_instances" /etc/sysctl.conf; then
  info "Already in /etc/sysctl.conf"
else
  echo "fs.inotify.max_user_instances=512" >> /etc/sysctl.conf
  info "Added to /etc/sysctl.conf (persists across reboots)"
fi

sysctl -p
success "System limits configured"

# ---------------------------------------------------------------------------
# Step 4 — Download and Install JFrog Artifactory
# ---------------------------------------------------------------------------
if $SKIP_JFROG; then
  warn "Skipping JFrog installation (--skip-jfrog)"
else
  section "Step 4 — Download and Install JFrog Artifactory"

  if systemctl is-active --quiet artifactory.service 2>/dev/null; then
    success "JFrog Artifactory is already running — skipping install"
  else
    # Check for a local installer tarball first
    installer_tgz=$(ls jfrog-platform-trial-prox-*-deb.tar.gz 2>/dev/null | head -1 || true)

    if [[ -n "$installer_tgz" ]]; then
      info "Using local installer: $installer_tgz"
    else
      info "Downloading JFrog Platform Trial installer (latest version)..."
      wget -O jfrog-deb-installer.tar.gz \
        "https://releases.jfrog.io/artifactory/jfrog-prox/org/artifactory/pro/deb/jfrog-platform-trial-prox/[RELEASE]/jfrog-platform-trial-prox-[RELEASE]-deb.tar.gz"
      installer_tgz="jfrog-deb-installer.tar.gz"
    fi

    info "Extracting installer..."
    tar -xzf "$installer_tgz"

    info "Running JFrog installer (this may take a few minutes)..."
    install_dir=$(ls -d jfrog-platform-trial-pro*/ 2>/dev/null | head -1 || true)
    if [[ -z "$install_dir" ]]; then
      error "Could not find extracted JFrog installer directory"
      exit 1
    fi
    bash "${install_dir}install.sh"

    success "JFrog installed"
  fi

  # ---------------------------------------------------------------------------
  # Step 5 — Start JFrog services
  # ---------------------------------------------------------------------------
  section "Step 5 — Start JFrog Services"

  info "Starting artifactory.service..."
  systemctl start artifactory.service
  systemctl enable artifactory.service

  info "Starting xray.service..."
  systemctl start xray.service || warn "xray failed to start — not required for airgap asset upload"

  # ---------------------------------------------------------------------------
  # Step 6 — Wait for JFrog to respond
  # ---------------------------------------------------------------------------
  section "Step 6 — Wait for JFrog to be Ready"

  jfrog_url="http://localhost:${JFROG_PORT}/artifactory"
  info "Waiting for JFrog at $jfrog_url (up to 3 minutes)..."

  max_wait=180
  elapsed=0
  until curl -sf "$jfrog_url/api/system/ping" 2>/dev/null | grep -q "OK"; do
    if [[ $elapsed -ge $max_wait ]]; then
      error "JFrog did not become ready within ${max_wait}s"
      error "Check status: systemctl status artifactory.service"
      error "Check logs:   journalctl -u artifactory.service -n 50"
      exit 1
    fi
    echo -n "."
    sleep 5
    elapsed=$((elapsed+5))
  done
  echo ""
  success "JFrog is ready at $jfrog_url"
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
echo "============================================================"
success "VM1 setup complete!"
echo ""
echo "Installed tools:"
for cmd in curl wget git jq skopeo helm python3 pip3 ansible ansible-galaxy; do
  if command -v "$cmd" &>/dev/null; then
    echo "  ✓ $cmd"
  else
    echo "  ✗ $cmd (missing)"
  fi
done

if ! $SKIP_JFROG; then
  echo ""
  echo "JFrog Artifactory is running at http://localhost:${JFROG_PORT}"
  echo "Default credentials: admin / password"
  echo ""
  echo "============================================================"
  echo "  NEXT: Activate the JFrog license before running script 2"
  echo "============================================================"
  echo ""
  echo "  1. Access the JFrog UI:"
  echo "     - From VM1 directly: http://localhost:${JFROG_PORT}"
  echo "     - From your local machine via SSH tunnel:"
  echo "       ssh -L ${JFROG_PORT}:localhost:${JFROG_PORT} user@<VM1-IP> -N"
  echo "       then open: http://localhost:${JFROG_PORT}"
  echo ""
  echo "  2. Log in with: admin / password"
  echo "     (change password when prompted)"
  echo ""
  echo "  3. Activate license:"
  echo "     Admin → Artifactory License → paste trial key → Save"
  echo "     (Get a free trial key at https://jfrog.com/start-free/)"
  echo ""
fi

echo "  Once the license is active, run script 2:"
echo ""
echo "  ./jfrog-setup.sh \\"
echo "    --jfrog-url http://localhost:${JFROG_PORT}/artifactory \\"
echo "    --jfrog-user admin \\"
echo "    --jfrog-pass <password> \\"
echo "    --dockerhub-user <dockerhub-username> \\"
echo "    --dockerhub-pass <dockerhub-pat>"
echo "============================================================"
