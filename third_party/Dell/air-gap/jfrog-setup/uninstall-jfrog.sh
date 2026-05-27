#!/usr/bin/env bash
# Copyright (C) 2025-2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# uninstall-jfrog.sh
#
# Reverses everything installed by jfrog-installation.sh on VM1:
#   - Stops and removes JFrog Artifactory and Xray services
#   - Removes JFrog packages, data, config, and logs
#   - Removes Helm
#   - Reverts fs.inotify.max_user_instances sysctl change
#   - Removes apt packages installed by jfrog-installation.sh
#
# Usage:
#   sudo ./uninstall-jfrog.sh [OPTIONS]
#
# Options:
#   --keep-packages   Skip removal of apt packages (curl, wget, git, etc.)
#   --keep-data       Skip removal of JFrog data directories (preserves /opt/jfrog)
#   -h, --help        Show this help message

set -euo pipefail

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
KEEP_PACKAGES=false
KEEP_DATA=false

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
    --keep-packages) KEEP_PACKAGES=true; shift ;;
    --keep-data)     KEEP_DATA=true; shift ;;
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
echo "  VM1 Uninstall — JFrog Artifactory + Prerequisites"
echo "  Keep apt packages: $KEEP_PACKAGES"
echo "  Keep JFrog data:   $KEEP_DATA"
echo "============================================================"
echo ""
warn "This will permanently remove JFrog Artifactory and all its data."
read -r -p "Are you sure you want to continue? (yes/no): " confirm
if [[ "$confirm" != "yes" ]]; then
  info "Aborted."
  exit 0
fi

# ---------------------------------------------------------------------------
# Step 1 — Stop and disable JFrog services
# ---------------------------------------------------------------------------
section "Step 1 — Stop and Disable JFrog Services"

for svc in xray artifactory; do
  if systemctl is-active --quiet "${svc}.service" 2>/dev/null; then
    info "Stopping ${svc}.service..."
    systemctl stop "${svc}.service"
    success "${svc}.service stopped"
  else
    info "${svc}.service is not running — skipping"
  fi

  if systemctl is-enabled --quiet "${svc}.service" 2>/dev/null; then
    info "Disabling ${svc}.service..."
    systemctl disable "${svc}.service"
    success "${svc}.service disabled"
  fi
done

# ---------------------------------------------------------------------------
# Step 2 — Remove JFrog packages
# ---------------------------------------------------------------------------
section "Step 2 — Remove JFrog Packages"

JFROG_PACKAGES=(artifactory xray jfrog-platform)

for pkg in "${JFROG_PACKAGES[@]}"; do
  if dpkg -l "$pkg" &>/dev/null 2>&1; then
    info "Removing package: $pkg..."
    apt-get remove --purge -y "$pkg"
    success "$pkg removed"
  else
    info "$pkg not installed — skipping"
  fi
done

info "Removing PostgreSQL installed by JFrog..."
systemctl stop postgresql 2>/dev/null || true
apt-get remove --purge -y postgresql postgresql-* 2>/dev/null || true
rm -rf /var/lib/postgresql /etc/postgresql /etc/postgresql-common
success "PostgreSQL removed"
info "Running apt autoremove..."
apt-get autoremove -y

# ---------------------------------------------------------------------------
# Step 3 — Remove JFrog data, config, and logs
# ---------------------------------------------------------------------------
section "Step 3 — Remove JFrog Data and Config"

if $KEEP_DATA; then
  warn "--keep-data set: skipping removal of JFrog directories"
else
  JFROG_DIRS=(
    /opt/jfrog
    /etc/opt/jfrog
    /var/opt/jfrog
    /var/log/jfrog
    /tmp/jfrog
    /tmp/artifactory
  )

  for dir in "${JFROG_DIRS[@]}"; do
    if [[ -d "$dir" ]]; then
      info "Removing $dir..."
      rm -rf "$dir"
      success "$dir removed"
    else
      info "$dir not found — skipping"
    fi
  done

  # Remove systemd unit files left behind by the installer
  for unit_file in /etc/systemd/system/artifactory.service \
                   /etc/systemd/system/xray.service \
                   /lib/systemd/system/artifactory.service \
                   /lib/systemd/system/xray.service; do
    if [[ -f "$unit_file" ]]; then
      info "Removing $unit_file..."
      rm -f "$unit_file"
    fi
  done
  systemctl daemon-reload
  success "Systemd units cleaned up"

  # Remove extracted installer directories left in the working directory
  installer_dirs=$(ls -d jfrog-platform-trial-pro*/ 2>/dev/null || true)
  if [[ -n "$installer_dirs" ]]; then
    info "Removing extracted installer directories..."
    rm -rf $installer_dirs
    success "Installer directories removed"
  fi

  # Remove downloaded installer tarballs
  for f in jfrog-platform-trial-prox-*.tar.gz jfrog-deb-installer.tar.gz; do
    if [[ -f "$f" ]]; then
      info "Removing $f..."
      rm -f "$f"
    fi
  done
fi

# ---------------------------------------------------------------------------
# Step 4 — Remove Helm
# ---------------------------------------------------------------------------
section "Step 4 — Remove Helm"

if command -v helm &>/dev/null; then
  helm_path=$(command -v helm)
  info "Removing helm from $helm_path..."
  rm -f "$helm_path"
  success "helm removed"
else
  info "helm not found — skipping"
fi

# ---------------------------------------------------------------------------
# Step 5 — Revert sysctl changes
# ---------------------------------------------------------------------------
section "Step 5 — Revert sysctl Changes"

if grep -q "fs.inotify.max_user_instances" /etc/sysctl.conf; then
  info "Removing fs.inotify.max_user_instances from /etc/sysctl.conf..."
  sed -i '/fs\.inotify\.max_user_instances/d' /etc/sysctl.conf
  sysctl -p
  success "sysctl change reverted"
else
  info "No inotify entry found in /etc/sysctl.conf — skipping"
fi

# ---------------------------------------------------------------------------
# Step 6 — Remove apt packages installed by jfrog-installation.sh
# ---------------------------------------------------------------------------
section "Step 6 — Remove apt Packages"

if $KEEP_PACKAGES; then
  warn "--keep-packages set: skipping removal of apt packages"
else
  warn "The following packages will be removed. Some (curl, git, python3) may be"
  warn "used by other tools on this machine. Use --keep-packages to skip this step."

  PACKAGES=(
    skopeo
    ansible
    jq
    net-tools
    vim
    software-properties-common
    gnupg
    lsb-release
    unzip
    wget
    curl
    git
    ca-certificates
    python3-pip
    python3
  )

  installed=()
  for pkg in "${PACKAGES[@]}"; do
    if dpkg -l "$pkg" &>/dev/null 2>&1; then
      installed+=("$pkg")
    fi
  done

  if [[ ${#installed[@]} -gt 0 ]]; then
    info "Removing: ${installed[*]}"
    apt-get remove --purge -y "${installed[@]}"
    apt-get autoremove -y
    success "apt packages removed"
  else
    info "No matching packages found — skipping"
  fi
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
echo "============================================================"
success "Uninstall complete!"
echo ""
echo "Removed:"
echo "  ✓ JFrog Artifactory and Xray services"
echo "  ✓ JFrog packages (artifactory, xray, jfrog-platform)"
if ! $KEEP_DATA; then
  echo "  ✓ JFrog data and config (/opt/jfrog, /etc/opt/jfrog, ...)"
fi
echo "  ✓ Helm"
echo "  ✓ sysctl fs.inotify.max_user_instances setting"
if ! $KEEP_PACKAGES; then
  echo "  ✓ apt packages installed by jfrog-installation.sh"
fi
echo "============================================================"
