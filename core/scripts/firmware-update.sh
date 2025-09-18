#!/bin/bash

set -e

# ------------------------
# Parse Arguments
# ------------------------
FORCE_DOWNGRADE=false

for arg in "$@"; do
  if [[ "$arg" == "--force" ]]; then
    FORCE_DOWNGRADE=true
  elif [[ "$arg" != -* ]]; then
    VERSION="$arg"
  fi
done

if [[ -z "$VERSION" ]]; then
  echo "Usage: $0 <version> [--force]"
  echo "Example: $0 1.21.1"
  exit 1
fi

INSTALLER_URL="https://vault.habana.ai/artifactory/gaudi-installer/${VERSION}/habanalabs-installer.sh"

# ------------------------
# Version Comparison Function
# ------------------------
version_to_int() {
  IFS='.' read -r major minor patch <<< "$1"
  printf "%d%03d%03d\n" "$major" "$minor" "$patch"
}

# ------------------------
# Get Installed Driver Version
# ------------------------
INSTALLED_DRIVER_VERSION=$(hl-smi | grep "Driver Version" | awk -F':' '{print $2}' | xargs | cut -d'-' -f1)

if [[ -n "$INSTALLED_DRIVER_VERSION" ]]; then
  installed_int=$(version_to_int "$INSTALLED_DRIVER_VERSION")
  requested_int=$(version_to_int "$VERSION")

  if (( installed_int >= requested_int )); then
    if [[ "$FORCE_DOWNGRADE" == false ]]; then
      echo "Installed Habana driver version ($INSTALLED_DRIVER_VERSION) is already equal to or newer than requested version ($VERSION)."
      echo "No upgrade necessary. Use --force to override."
      exit 0
    else
      echo "Warning: Installed version ($INSTALLED_DRIVER_VERSION) is newer than requested ($VERSION), but proceeding due to --force flag."
    fi
  fi
fi

# ------------------------
# Ensure /etc/sysctl.conf Exists
# ------------------------
if [[ ! -f /etc/sysctl.conf ]]; then
  echo "/etc/sysctl.conf not found. Creating it..."
  sudo touch /etc/sysctl.conf
fi

# ------------------------
# Previous Version Info
# ------------------------
echo "Previous Driver Version    : ${INSTALLED_DRIVER_VERSION:-Not Found}"
NIC_VERSION=$(hl-smi | grep "Nic Driver Version" | awk -F':' '{print $2}' | xargs)
FIRMWARE_VERSION=$(hl-smi -L | grep "Firmware \[SPI\] Version" | head -n 1 | awk -F':' '{print $2}' | xargs)
echo "Previous NIC Version       : ${NIC_VERSION:-Not Found}"
echo "Previous Firmware Version  : ${FIRMWARE_VERSION:-Not Found}"
echo

# ------------------------
# Download Installer
# ------------------------
echo "Downloading Habana installer for version $VERSION..."
rm -f habanalabs-installer.sh
wget -nv "$INSTALLER_URL" -O habanalabs-installer.sh

echo "Making installer executable..."
chmod +x habanalabs-installer.sh

# ------------------------
# Uninstall Previous
# ------------------------
echo "Uninstalling any previous Habana installation..."
yes | ./habanalabs-installer.sh uninstall

# ------------------------
# Install New Version
# ------------------------
echo "Running Habana installer..."
yes | ./habanalabs-installer.sh install --type base

# ------------------------
# Firmware Upgrade
# ------------------------

# Step 1: Unload modules based on installed version
echo "Unloading kernel modules based on installed version ($INSTALLED_DRIVER_VERSION)..."
if [[ -n "$INSTALLED_DRIVER_VERSION" ]]; then
    major=$(echo "$INSTALLED_DRIVER_VERSION" | cut -d. -f1)
    minor=$(echo "$INSTALLED_DRIVER_VERSION" | cut -d. -f2)

    if [[ "$major" -eq 1 && "$minor" -lt 21 ]]; then
        sudo modprobe -r habanalabs
        sudo modprobe -r habanalabs_cn
        sudo modprobe -r habanalabs_ib
        sudo modprobe -r habanalabs_en
    else
        sudo modprobe -r habanalabs_ib
        sudo modprobe -r habanalabs_en
        sudo modprobe -r habanalabs_cn
        sudo modprobe -r habanalabs
        sudo modprobe -r habanalabs_compat
    fi
fi

# Step 2: Firmware update (always reload modules even if this fails)
echo "Running firmware upgrade..."
if ! sudo hl-fw-loader -y; then
    echo "Warning: Firmware upgrade failed. Will reload kernel modules to restore system state."
    FW_UPGRADE_FAILED=true
else
    FW_UPGRADE_FAILED=false
fi

# Step 3: Load modules based on target version (always run)
echo "Loading kernel modules based on target version ($VERSION)..."
major=$(echo "$VERSION" | cut -d. -f1)
minor=$(echo "$VERSION" | cut -d. -f2)

if [[ "$major" -eq 1 && "$minor" -lt 21 ]]; then
    sudo modprobe habanalabs
    sudo modprobe habanalabs_cn
    sudo modprobe habanalabs_ib
    sudo modprobe habanalabs_en
else
    sudo modprobe habanalabs_compat
    sudo modprobe habanalabs
    sudo modprobe habanalabs_cn
    sudo modprobe habanalabs_en
    sudo modprobe habanalabs_ib
fi

if [[ "$FW_UPGRADE_FAILED" == true ]]; then
    echo "Firmware upgrade failed, but kernel modules have been reloaded to avoid system impact."
fi

# ------------------------
# Install Matching Runtime
# ------------------------
echo "Installing habanalabs-container-runtime..."
sudo apt update
echo "Searching for habanalabs-container-runtime matching version $VERSION..."

RUNTIME_LINE=$(apt list -a habanalabs-container-runtime 2>/dev/null | grep "$VERSION" | head -n1)

if [[ -n "$RUNTIME_LINE" ]]; then
  PKG_NAME=$(echo "$RUNTIME_LINE" | cut -d/ -f1)
  PKG_VERSION=$(echo "$RUNTIME_LINE" | awk '{print $2}')
  echo "Installing $PKG_NAME version $PKG_VERSION..."
  sudo apt install -y "${PKG_NAME}=${PKG_VERSION}"
else
  echo "Warning: No habanalabs-container-runtime package found matching version $VERSION"
  echo "Installing latest available version instead..."
  sudo apt install -y habanalabs-container-runtime
fi

# ------------------------
# Show Updated Versions
# ------------------------
echo
echo "Fetching updated Habana versions..."
sleep 3
NEW_DRIVER_VERSION=$(hl-smi | grep "Driver Version" | awk -F':' '{print $2}' | xargs | cut -d'-' -f1)
NEW_NIC_VERSION=$(hl-smi | grep "Nic Driver Version" | awk -F':' '{print $2}' | xargs | cut -d'-' -f1)
NEW_FW_VERSION=$(hl-smi -L | grep "Firmware \[SPI\] Version" | head -n 1 | grep -oP 'hl-gaudi2-\K[\d\.]+')
NEW_RUNTIME_VERSION=$(apt list --installed 2>/dev/null | grep '^habanalabs-container-runtime/' | awk '{print $2}' | cut -d',' -f1)

echo "Updated Driver Version     : ${NEW_DRIVER_VERSION:-Not Found}"
echo "Updated NIC Version        : ${NEW_NIC_VERSION:-Not Found}"
echo "Updated Firmware Version   : ${NEW_FW_VERSION:-Not Found}"
echo "Updated Container Runtime   : ${NEW_RUNTIME_VERSION:-Not Found}"