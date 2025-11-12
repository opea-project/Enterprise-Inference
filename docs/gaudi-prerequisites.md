# Gaudi Node Requirements and Setup Guide

This guide helps verify and automatically install the latest firmware and driver version for **Habana Gaudi** nodes in your Kubernetes or Standalone Environment.

# What You Need
- Intel® Gaudi® cards installed in your system 
- Linux operating system
- Internet connection
- Root/sudo privileges

### Enable IOMMU Passthrough

Enabling IOMMU passthrough is required only for Ubuntu 24.04.2/22.04.5 with Linux kernel 6.8. Skip this section if a different OS or kernel version is used.

To enable IOMMU passthrough:

1. Add `GRUB_CMDLINE_LINUX_DEFAULT="iommu=pt intel_iommu=on"` to `/etc/default/grub`.
2. Run `sudo update-grub`.
3. Reboot the system.

For more details, see the [Ubuntu documentation](https://bugs.launchpad.net/ubuntu/+source/linux-gcp-6.8/+bug/2085904).

----


#### Step 1: Check Firmware Version
```bash
hl-smi -L | grep SPI
```
You'll see something like:
```
Firmware [SPI] Version : Preboot version hl-gaudi2-1.20.0-fw-58.0.0-sec-9 (Jan 16 2025 - 17:51:04)
```
###### For visual assistance, refer to the following snapshot for Firmware version:

<img src="../docs/pictures/Enterprise-Inference-Gaudi-Firmware-version.png" alt="AI Inference Firmware Snapshot" width="800" height="120"/>   
   

#### Step 2: Check Driver Version
Use the following commands to check the required driver version installed on your Gaudi nodes:

```bash
hl-smi 
```
You'll see something like:
```
+-----------------------------------------------------------------------------+
| HL-SMI Version:                              hl-1.22.1-fw-61.4.2.1           |
| Driver Version:                                    1.22.0-5f8fa9f            |
| Nic Driver Version:                                 1.22.0-5f8fa9f           |
|-------------------------------+----------------------+----------------------+
```
###### For visual assistance, refer to the following snapshot for Driver version:

<img src="../docs/pictures/Enterprise-Inference-Gaudi-Driver-version.png" alt="AI Inference Driver Snapshot" width="800" height="120"/>    
   
#### Step 3: Check Runtime Version

```bash
dpkg -l | grep habanalabs-container-runtime
```
You'll see something like:
```
ii  habanalabs-container-runtime 1.22.1-6  HABANA container runtime
```

#### Step 4: Check if IOMMU Passthrough Needs to be Enabled
> **Important:** If OS Ubuntu 24.04/22.04.5 with Linux kernel 6.8 is used, _IOMMU Passthrough must be enabled_ to prevent garbled output during LLM inference.
To check if it is already enabled:
```bash
cat /proc/cmdline
```
Look for *iommu=pt* and *intel_iommu=on* in the output.

Otherwise, follow these [instructions](https://docs.habana.ai/en/latest/Installation_Guide/Driver_Installation.html#enable-iommu-passthrough) to enable IOMMU Passthrough.

#### Updating Your System (Automated)

The platform now includes an automated firmware and driver update script that handles the complete upgrade process safely and efficiently.

#### Automated Installation/Upgrade Process

Navigate to the scripts directory and run the automated firmware update script:

```bash
cd core/scripts/
chmod +x firmware-update.sh

# Upgrade to a specific version (e.g., 1.22.0)
./firmware-update.sh 1.22.0

# Force downgrade if needed (e.g., from 1.21.1 to 1.20.0)  
./firmware-update.sh 1.20.0 --force
```

#### What the Automation Does

The script automatically handles:
- ✅ **Version validation** - Prevents unnecessary upgrades
- ✅ **Driver uninstallation** - Safely removes existing installation
- ✅ **Driver installation** - Downloads and installs target version
- ✅ **Firmware upgrade** - Updates card firmware using `hl-fw-loader`
- ✅ **Kernel module management** - Version-aware loading/unloading
- ✅ **Container runtime setup** - Installs matching runtime version
- ✅ **Pre/post validation** - Shows version information before and after

#### Manual Verification (Optional)

After running the automated script, you can verify the installation:

# For Kubernetes Users
After the automated upgrade, check that your cards are properly recognized:
```bash
kubectl get nodes
kubectl describe node node-name
```
Look for:
```
Capacity:  
  habana.ai/gaudi:    8  
Allocatable: 
  habana.ai/gaudi:    8
```
If the numbers don't match, run:

```bash
kubectl rollout restart ds habana-ai-device-plugin-ds -n habana-ai-operator
```
> **For detailed documentation, refer to the official guide:** [Intel® Gaudi® Software Installation Documentation](https://docs.habana.ai/en/latest/Installation_Guide/Driver_Installation.html)
>
> **For automation script details:** See [Firmware Update Script Documentation](../core/scripts/README.md)
>
> **Note**: It is recommended to reboot the device after firmware/driver updates to ensure complete initialization. The automation script provides comprehensive version validation before and after the upgrade process.
> If for some reason rebooting the device is not possible, please try to restart habana device plugin as documented above if Model pods go to pending due to workload nodes not getting allocatable "habana.ai/gaudi" equal to capacity as documented above.

