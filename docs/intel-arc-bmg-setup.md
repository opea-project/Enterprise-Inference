# Intel® Arc™ Battlemage (BMG) GPU Setup Guide

<!-- Copyright (C) 2025-2026 Intel Corporation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

## Overview

This guide describes how to deploy Intel® AI for Enterprise Inference on Intel® Arc™ Battlemage (BMG) GPU hardware (Arc Pro B-series, e.g., B60, B70) for testing pourposes.

Intel Arc Battlemage GPUs are supported via the Intel GPU Plugin for Kubernetes and the XPU backend in vLLM.

## Supported Models

The following models have been enabled for testing porpose on Intel Arc Battlemage GPU deployment:

| Menu # | Model ID | VRAM Required |
|--------|----------|---------------|
| 36 | Qwen/Qwen2.5-Coder-3B-Instruct *(default)* | ~4 GB |

## Prerequisites

### Hardware Requirements

- Intel® Arc™ Battlemage GPU
- Host system with PCIe Gen5 x16 slot
- Ubuntu 25.10

### Software Requirements

Before deploying, ensure the following are installed on **all worker nodes** with BMG GPUs:

#### 1. Enteprise inference prerequisites: [docs/intel-arc-bmg-setup.md](intel-arc-bmg-setup.md)

#### 2. Intel GPU Drivers

Install Intel GPU drivers https://dgpu-docs.intel.com/installation-guides/installing-packages-from-the-intel-ppa.html
```

#### 3. Verify Intel GPU is detected

```bash
# Verify GPU detection
clinfo | grep "Device Name"
# Should show: Intel(R) Arc(TM) B580 Graphics (or similar)

ls /dev/dri/
# Should show renderD128 (or similar render node)
```

## Configuration

### inference-config.cfg

Set `device=xpu` in your `core/inventory/inference-config.cfg`:

```ini
# Hardware selection: 'cpu' for Xeon CPU, 'hpu'/'gpu'/'gaudi2'/'gaudi3' for Gaudi, 'xpu'/'bmg' for Intel Arc Battlemage GPU
device=xpu

# Select BMG-compatible models (31-36). Default is 36 (Qwen2.5-Coder-3B-Instruct).
models=36

# Other settings remain the same
deploy_kubernetes_fresh=on
deploy_ingress_controller=on
deploy_keycloak_apisix=on
deploy_llm_models=on
```

### Command Line Usage

```bash
# Deploy with Intel Arc Battlemage GPU (Qwen2.5-Coder-3B-Instruct is the default XPU model)
./inference-stack-deploy.sh \
    --cluster-url "https://my-cluster.example.com" \
    --cert-file "/path/to/cert.pem" \
    --key-file "/path/to/key.pem" \
    --keycloak-client-id "my-client-id" \
    --keycloak-admin-user "admin" \
    --keycloak-admin-password "changeme" \
    --hugging-face-token "hf_your_token" \
    --models "36" \
    --device "xpu"
```

## Deployment Architecture

For Intel Arc Battlemage GPU deployments, the Intel GPU Plugin is used instead of the Habana AI Operator:

```
+--------------------------------------------------+
|              Kubernetes Cluster                  |
|                                                  |
|  +--------------------------------------------+ |
|  |     Intel GPU Plugin (DaemonSet)           | |
|  |  - Exposes gpu.intel.com/xe resource       | |
|  |  - Manages Arc B-series GPU allocation     | |
|  +--------------------------------------------+ |
|                                                  |
|  +--------------------------------------------+ |
|  |     vLLM Pod (XPU Backend)                 | |
|  |  - Image: opea/vllm-xpu                    | |
|  |  - Device: xpu (Intel Arc GPU)             | |
|  |  - Resources: gpu.intel.com/xe: 1          | |
|  +--------------------------------------------+ |
+--------------------------------------------------+
```

## Intel GPU Plugin

The Intel GPU Plugin for Kubernetes is automatically deployed when `device=xpu`. It:

- Exposes `gpu.intel.com/xe` resource on nodes with Intel Arc GPUs
- Enables Kubernetes workloads to request Intel Arc GPU resources
- Uses Node Feature Discovery (NFD) to detect GPU-capable nodes

**Plugin Version**: 0.36.0 (configurable in `inference-metadata.cfg`)

## vLLM XPU Backend

Intel Arc BMG GPU deployments use vLLM with the XPU backend:

- **Image**: `intel/vllm:0.14.0-xpu`
- **Device**: set via `VLLM_TARGET_DEVICE=xpu` (baked into the image; do not pass `--device xpu` as a CLI argument)
- **Precision**: `float16` (optimized for Arc GPU)
- **Block size**: 16 (optimized for XPU KV cache)
- **GPU Memory Utilization**: 90%

## Troubleshooting

### Common Issues

1. **GPU not detected**: Ensure Intel GPU drivers are installed and `/dev/dri/renderD128` exists
2. **NFD label missing**: Label the node manually with `intel.feature.node.kubernetes.io/gpu=true`
3. **Out of memory**: Use a smaller model or upgrade to B770 (16GB GDDR6)
4. **XPU backend error**: Verify `intel/vllm:0.17.0-xpu` image is available and can pull from registry

### CoreDNS Crash-Loop (Keycloak / PostgreSQL DNS failure)

**Symptom:** Keycloak pod repeatedly logs `cannot resolve host "keycloak-postgresql"`, CoreDNS pod is in `CrashLoopBackOff` with:
```
[FATAL] plugin/loop: Loop (127.0.0.1:... -> :53) detected for zone "."
```

**Cause:** On systems using `systemd-resolved`, `/etc/resolv.conf` is a symlink to
`/run/systemd/resolve/resolv.conf`, which lists the `nodelocaldns` address 
as the first nameserver. CoreDNS `forward . /etc/resolv.conf` then forwards external queries
to nodelocaldns, which forwards them back to CoreDNS — creating a loop that the `loop` plugin
kills CoreDNS over.

**Fix:** 
sudo rm -f /etc/resolv.conf
sudo ln -s /run/systemd/resolve/resolv.conf /etc/resolv.conf

## Supported Platforms

- Ubuntu 25.10

## References

- [Intel GPU Plugin for Kubernetes](https://github.com/intel/intel-device-plugins-for-kubernetes)
- [vLLM XPU Backend Documentation](https://docs.vllm.ai/en/latest/getting_started/xpu-installation.html)
- [Intel Arc GPU Driver Installation](https://dgpu-docs.intel.com/driver/client/overview.html)
- [Intel Extension for PyTorch (IPEX)](https://intel.github.io/intel-extension-for-pytorch/)
