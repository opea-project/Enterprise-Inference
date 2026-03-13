## Single Node OpenShift (SNO) Installation Using Assisted Installer

This repository provides a **comprehensive guide** for installing **Single Node OpenShift (SNO)** using the **Red Hat Assisted Installer**.  
It is intended for **edge deployments, lab environments, proof-of-concepts (PoCs), and development workloads**, and can be used on **bare metal servers**.

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Installation Procedure](#installation-procedure)
- [Accessing the SNO Node](#accessing-the-sno-node)
- [Post-Installation Storage Setup](#post-installation-storage-setup)
- [Validation & Health Checks](#validation--health-checks)

---

## Overview

**Single Node OpenShift (SNO)** is a deployment model where all OpenShift components—control plane and worker—run on a **single node**.

The **Red Hat Assisted Installer** streamlines OpenShift installation by performing **preflight checks, hardware validation, network validation, and operator readiness checks** before cluster installation.

**This is the official Red Hat reference document for SNO installation:** https://docs.redhat.com/en/documentation/openshift_container_platform/4.12/html/installing_on_a_single_node/install-sno-installing-sno

---

## Architecture

In a Single Node OpenShift deployment:

- One node acts as:
  - Control Plane
  - Worker
  - etcd member
- High availability is **not provided**
- External load balancers are **not required**
- Ingress, API, and applications are exposed directly from the node

---

## Prerequisites

### Infrastructure Requirements

| Resource | Minimum | Recommended |
|--------|---------|-------------|
| CPU | 4 vCPU | 8+ vCPU |
| Memory | 16 GB | 32+ GB |
| Disk | 120 GB | 250+ GB |
| Network | Outbound Internet access | Stable, low-latency |
| DNS | Required | Highly reliable |

> **Note:** For workloads such as AI/ML inference, OpenShift Virtualization, or observability-heavy clusters, allocate additional CPU, memory, and disk.

### Network Requirements

- Outbound internet access is required during installation
- NTP must be enabled and system clocks synchronized
- Firewalls must allow required OpenShift ports
  
---

## Installation Procedure
### Step 1: Create the Cluster

1. Open the OpenShift Assisted Installer UI:
```bash
https://console.redhat.com/openshift/assisted-installer/clusters
```
2. Click Create new cluster
3. Select:
   - **Deployment type:** Single Node OpenShift (SNO)
   - **Platform:** Bare metal / Other
4. Provide cluster details:
    - Cluster name
    - Base domain (example: example.com)
    - OpenShift version
5. Click Create cluster

### Step 2: Add Host and Generate Discovery ISO

1. Navigate to the Hosts tab
2. Click Add host
3. Select:
   - Full Discovery ISO (strongly recommended)
4. Click Generate Discovery ISO
5. Download the ISO
The Full Discovery ISO reduces network dependencies and significantly improves installation reliability.

### Step 3: Boot the Target Machine

1. Boot the bare-metal server using the Discovery ISO
2. Wait for the host to appear in the Assisted Installer UI
3. Confirm:
    - Host discovery is successful
    - CPU, memory, and disk validations pass
    - Network connectivity checks pass
    - All operator validations are successful

### Step 4: Install the Cluster

1. Click Install Cluster
2. Monitor progress in the Assisted Installer UI
3. Installation typically completes in 30–60 minutes

> Note: Do not reboot or shut down the node during installation.

---

## Accessing the SNO Node

### Copy kubeconfig to the Node

```bash
scp ~/.kube/config user@<NODE_IP>:/home/user/admin.kubeconfig
```
> **Note:** RHCOS restricts root access and /home/user is writable

### SSH into the Node
```bash
ssh user@<NODE_IP>
```
### Switch to Root
```bash
sudo -i
```
> **Note:** RHCOS uses sudo-based privilege escalation. Direct root login is intentionally restricted.

Configure kubeconfig for Root
```bash
mv /home/user/admin.kubeconfig /root/admin.kubeconfig
export KUBECONFIG=/root/admin.kubeconfig
echo 'export KUBECONFIG=/root/admin.kubeconfig' >> ~/.bashrc
source ~/.bashrc
```
### Verify OpenShift Access (From Node)
```bash
oc whoami
oc get nodes
```
**Expected:**

  - User: system:admin
  - Node: Ready
---

## Post-Installation Storage Setup

SNO does not support dynamic storage provisioning. Local storage must be explicitly configured.

**Step 1: Install Local Storage Operator**
```bash
oc create namespace openshift-local-storage
```

```bash
oc apply -f - <<EOF
apiVersion: operators.coreos.com/v1
kind: OperatorGroup
metadata:
  name: local-storage-operator-group
  namespace: openshift-local-storage
spec:
  targetNamespaces:
  - openshift-local-storage
---
apiVersion: operators.coreos.com/v1alpha1
kind: Subscription
metadata:
  name: local-storage-operator
  namespace: openshift-local-storage
spec:
  channel: stable
  name: local-storage-operator
  source: redhat-operators
  sourceNamespace: openshift-marketplace
EOF
```
**Step 2: Verify Operator Is Running**
```bash
oc get pods -n openshift-local-storage
```
Expected:
  - local-storage-operator → Running
  - diskmaker-manager → Running

**Step 3: Identify a Free Disk**
```bash
lsblk
```
Ensure the disk is:
  - Not mounted
  - Not already used
  - Large enough for workloads
Example disk:
```bash
/dev/nvme5n1
```
**Step 4: Bind Disk to Local Storage (Create LocalVolume)**

Replace "SNO_HOSTNAME"with your cluster ip

```bash
cat <<EOF | oc apply -f -
apiVersion: local.storage.openshift.io/v1
kind: LocalVolume
metadata:
  name: local-storage
  namespace: openshift-local-storage
spec:
  nodeSelector:
    nodeSelectorTerms:
    - matchExpressions:
      - key: kubernetes.io/hostname
        operator: In
        values:
        - <SNO_HOSTNAME>
  storageClassDevices:
  - storageClassName: local-sc
    volumeMode: Filesystem
    fsType: xfs
    devicePaths:
    - /dev/nvme5n1
EOF
```
> **Note:** The Local Storage Operator creates only **one PV per disk**. Additional PVCs require additional disks or partitions.

---

## Validation & Health Checks

### Validate cluster health:
```bash
oc get nodes
oc get clusteroperators
```
All cluster operators should be Available=True.

### Verify StorageClass
```bash
oc get storageclass
```
**Expected:**

  - local-sc

### Check for pending PVCs:
```bash
oc get pvc -A
```
If PVC is Pending:
  - No free disk is assigned
  - A new disk must be added and bound via LocalVolume
