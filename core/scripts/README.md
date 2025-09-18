# Intel® Gaudi® Firmware and Driver Automation Scripts

This directory contains automation scripts for managing Intel® Gaudi® AI Accelerator firmware, drivers, and related components.

## Scripts Overview

### `firmware-update.sh`
Automated firmware and driver upgrade script for Intel® Gaudi® AI Accelerators.

#### Features
- **Version Management**: Intelligent version comparison to prevent unnecessary downgrades
- **Complete Automation**: Handles driver uninstallation, installation, firmware upgrade, and container runtime setup
- **Safe Module Management**: Properly unloads and reloads kernel modules based on version-specific requirements
- **Error Resilience**: Continues operation even if firmware upgrade fails to maintain system stability
- **Pre/Post Validation**: Shows version information before and after the upgrade process

#### Usage

```bash
# Basic usage - upgrade to specific version
./firmware-update.sh <version>

# Example: Upgrade to version 1.21.1
./firmware-update.sh 1.21.1

# Force downgrade (if newer version is already installed)
./firmware-update.sh 1.20.0 --force
```

#### Parameters
- `<version>`: Target Habana driver version (e.g., 1.21.1, 1.20.0)
- `--force`: Optional flag to force downgrade from newer to older version

#### What the Script Does

1. **Version Check**: Compares installed version with requested version
2. **Pre-upgrade Info**: Displays current driver, NIC, and firmware versions
3. **Download**: Fetches the official Habana installer for the specified version
4. **Uninstall**: Removes existing Habana installation
5. **Install**: Installs the new driver version
6. **Module Management**: 
   - Unloads kernel modules safely (version-aware)
   - Upgrades firmware using `hl-fw-loader`
   - Reloads modules with proper order
7. **Runtime Installation**: Installs matching `habanalabs-container-runtime`
8. **Validation**: Shows updated version information

#### Version-Specific Module Handling

The script intelligently handles kernel module loading/unloading based on version:

**For versions < 1.21.x:**
```bash
# Unload order
modprobe -r habanalabs habanalabs_cn habanalabs_ib habanalabs_en

# Load order  
modprobe habanalabs habanalabs_cn habanalabs_ib habanalabs_en
```

**For versions >= 1.21.x:**
```bash
# Unload order
modprobe -r habanalabs_ib habanalabs_en habanalabs_cn habanalabs habanalabs_compat

# Load order
modprobe habanalabs_compat habanalabs habanalabs_cn habanalabs_en habanalabs_ib
```

#### Prerequisites
- Ubuntu/Debian-based Linux system
- Root/sudo privileges
- Internet connection
- Intel® Gaudi® cards installed
- `hl-smi` tool available (from previous Habana installation)

#### Error Handling
- **Firmware Upgrade Failure**: Script continues and reloads modules to maintain system stability
- **Version Check**: Prevents unnecessary upgrades unless `--force` is used
- **Missing Files**: Creates required system files (`/etc/sysctl.conf`) if missing
- **Network Issues**: Proper error messages if download fails

#### Output Example
```bash
$ ./firmware-update.sh 1.21.1

Previous Driver Version    : 1.20.0
Previous NIC Version       : 1.20.0-e4fe12d
Previous Firmware Version  : Preboot version hl-gaudi2-1.20.0-fw-58.0.0-sec-9 (Jan 16 2025 - 17:51:04)

Downloading Habana installer for version 1.21.1...
Making installer executable...
Uninstalling any previous Habana installation...
Running Habana installer...
Unloading kernel modules based on installed version (1.20.0)...
Running firmware upgrade...
Loading kernel modules based on target version (1.21.1)...
Installing habanalabs-container-runtime...

Updated Driver Version     : 1.21.1
Updated NIC Version        : 1.21.1-a1b2c3d
Updated Firmware Version   : 1.21.1
Updated Container Runtime   : 1.21.1-543
```

#### Post-Upgrade Recommendations
1. **Reboot**: Recommended for complete system refresh
2. **Verification**: Run `hl-smi` to confirm proper installation
3. **Kubernetes**: If using Kubernetes, restart the Habana device plugin:
   ```bash
   kubectl rollout restart ds habana-ai-device-plugin-ds -n habana-ai-operator
   ```

### Other Scripts

#### `gaudi-firmware-driver-updater.sh`
Legacy firmware and driver update script (deprecated - use `firmware-update.sh` instead).

#### `keycloak-fetch-client-secret.sh`
Retrieves Keycloak client secrets for authentication setup.

#### `keycloak-realmcreation.sh`
Automates Keycloak realm creation and configuration.

## Support and Troubleshooting

### Common Issues

1. **"No upgrade necessary"**: Current version is already equal or newer
   - **Solution**: Use `--force` flag if downgrade is intended

2. **Module loading fails**: Kernel modules cannot be loaded
   - **Solution**: Reboot the system and try again

3. **Firmware upgrade fails**: `hl-fw-loader` returns error
   - **Solution**: Script continues automatically; reboot recommended

4. **Network timeout**: Cannot download installer
   - **Solution**: Check internet connectivity and firewall settings

### Getting Help

For issues with these scripts:
1. Check the [Gaudi Prerequisites Guide](../../docs/gaudi-prerequisites.md)
2. Refer to [Intel® Gaudi® Software Installation Documentation](https://docs.habana.ai/en/latest/Installation_Guide/Driver_Installation.html)
3. Open an issue in the project repository

## Integration with Enterprise Inference Platform

These scripts are part of the Intel® AI for Enterprise Inference platform automation suite. They ensure that Gaudi nodes meet the required firmware and driver versions before deploying AI inference workloads.

For complete deployment instructions, see the [main documentation](../../docs/README.md).
