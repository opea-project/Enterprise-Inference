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
| CPU | 8 vCPU | 16+ vCPU |
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

Open the OpenShift Assisted Installer UI and click on **Create Cluster**

```bash
https://console.redhat.com/openshift/assisted-installer/clusters
```
### Step 1: Configure cluster details

Provide the cluster details

- **Cluster Name** : Provide a name to the cluster (example: api)
- **Base Domain** : Enter your domain (example: example.com)
> Note: The system will automatically form the full cluster URL: api.api.example.com, This value is permanent and cannot be changed later
- **Openshift Version** : Select OpenShift version as 4.20.x (example: 4.20.17)
- **CPU architecture** : Select _x86_64_ as CPU architecture
- **Number of control plane nodes** : Select _1 (Single Node OpenShift)_ as control plane node

Next, under _operators_ leave everything default and move to next Page

### Step 2: Host Discovery (Generate and Boot Discovery ISO

- Click “Add host” and generate Discovery ISO
- Choose **Provisioning type** as _Full Discovery ISO_
- Paste your SSH public key (required for accessing the node later)
- Click Generate Discovery ISO
- Once the ISO is generated, save the URL or download the ISO, use this to boot your machine that will acts as openshift cluster

> Note: The Full Discovery ISO reduces network dependencies and significantly improves installation reliability.

### Step 3: Boot your server using the ISO

**Boot the server using the Discovery ISO**
- Mount the ISO (via iDRAC / USB)
- Reboot the server and ensure it boots from the ISO
- The system will start a lightweight discovery agent

**Wait for host detection in OpenShift UI**
- In Openshift UI, check host inventory status
- Confirm the host is listed with:
  Role: Control plane + Worker (SNO)
  Status: Ready

### Step 4: Install the Cluster

**Validate Storage configuration**

- Ensure correct installation disk is selected
- Verify additional disks are visible and not selected (to use later)

**Validate Networking configuration**
- Confirm correct IP address is assigned (DHCP or Static)
- Verify active NIC is detected

> Note: Ensure connectivity to required endpoints (DNS / API if applicable)

**Install Cluster**

- Click Install Cluster, installation typically completes in 30–60 minutes
- Once cluster is installed, download and save the kubeconfig file.
- Also, save the kubeadmin password.

> Note: Do not reboot or shut down the node during installation.

---

## Accessing the SNO Node

### Copy kubeconfig to the Node

- Replace PATH_TO_YOUR_KUBECONFIG_FILE below with the actual path of your downloaded kubeconfig file, Run this on your local machine.
- Replace NODE_IP with your actual IP
```bash
scp PATH_TO_YOUR_KUBECONFIG_FILE core@<NODE_IP>:/home/core/admin.kubeconfig
```
> **Note:** RHCOS restricts root access and /home/user is writable

### SSH into the Node

SSH into the node
```bash
ssh core@<NODE_IP>
```
### Switch to Root
```bash
sudo -i
```
> **Note:** RHCOS uses sudo-based privilege escalation. Direct root login is intentionally restricted.

Configure kubeconfig for Root
```bash
mv /home/core/admin.kubeconfig /root/admin.kubeconfig
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

SNO does not support dynamic storage provisioning by default. Local storage must be explicitly configured.

**Step 1: Install Local Storage Operator**
```bash
oc create namespace openshift-local-storage
```

**verify**
```bash
oc get csv -n openshift-local-storage
```
**expected**
```bash
local-storage-operator.vX.X.X   Succeeded
```
**Create Operator Group**
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
EOF
```
**Create Subscription**
```bash
oc apply -f - <<EOF
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
**verify**
```bash
oc get pods -n openshift-local-storage
```
**Expected:**
```bash
local-storage-operator-xxxxxxx 1/1 Running
```

**Step 2: Identify a Free Disk**
```bash
lsblk
```
Ensure the selected disk meets the following criteria:
  - Not mounted
  - Not already used
  - Large enough for workloads
Example disk:
```bash
/dev/nvme5n1
```
**Step 3: Create LocalVolume**

- Replace SNO_HOSTNAME with your cluster hostname (example: f4-4d-ad-04-86-37)
- Replace device paths with the available disks on your machine.

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
     - /dev/nvme0n1
     - /dev/nvme5n1
     - /dev/nvme7n1
EOF
```
> **Note:** The Local Storage Operator creates only **one PV per disk**. Additional PVCs require additional disks or partitions.

**Make local-sc as default storageclass**
```bash
oc patch storageclass local-sc \
  -p '{"metadata": {"annotations":{"storageclass.kubernetes.io/is-default-class":"true"}}}'
```

---

## Validation & Health Checks

### Validate cluster health:
```bash
oc get nodes
``
```bash
oc get clusteroperators
```
**Ensure:**
- Available = True
- Progressing = False
- Degraded = False

### Verify StorageClass
```bash
oc get storageclass
```
**Expected:**

  - local-sc

### Verify PV

```bash
oc get pv
```
**Expected:**
 ```bash
NAME                CAPACITY   ACCESS MODES   RECLAIM POLICY   STATUS      CLAIM   STORAGECLASS   AGE
local-pv-xxxx       3576Gi     RWO            Delete           Available           local-sc       5m
local-pv-yyyy       3576Gi     RWO            Delete           Available           local-sc       5m
local-pv-zzzz       3576Gi     RWO            Delete           Available           local-sc       5m
```