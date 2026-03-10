
# Troubleshooting Guide

This section provides common deployment and runtime issues observed during Intel® AI for Enterprise Inference setup — along with step-by-step resolutions.

**Issues:**
  1. [Deployment Fails During Bastion Setup](#1-Deployment-Fails-During-Bastion-Setup)
  2. [PVC Stuck in Pending State](#2-PVC-Stuck-in-Pending-State)
  3. [StatefulSet Pods Not Scheduling on SNO](#3-StatefulSet-Pods-Not-Scheduling-on-SNO)
  4. [Route Exists but API Is Not Reachable](#4-Route-Exists-but-API-Is-Not-Reachable)
  5. [Keycloak Token Generation Fails](#5-Keycloak-Token-Generation-Fails)
     
---

### 1. Deployment Fails During Bastion Setup

Deployment stops early with errors such as:

Failed to update apt cache
Bastion node setup failed. Exiting.

**Root Cause**

EI bastion setup assumes: 
- A multi-node cluster
- A mutable OS
- Working `apt` repositories

**These assumptions are invalid for SNO brownfield deployments.**

  - SNO does not require a bastion
  - RHCOS is immutable
  - Bastion playbooks are incompatible

**Fix**
```bash
export EI_SKIP_BASTION_SETUP=true
export SKIP_BASTION_SETUP=true
./inference-stack-deploy.sh
```

> **Note:**
> - Bastion is not required for SNO
> - Skipping bastion is expected and correct
> - Do not attempt to fix apt just to satisfy bastion logic

---

### 2. PVC Stuck in Pending State

Verify:

PVC shows:
> status : pending

And pod describe shows
> waiting for first consumer 0/1 nodes didn’t find available PVs

**Verify Local Storage Operator**
```bash
oc get pods -n openshift-local-storage
```

Expected:
- local-storage-operator → Running
- diskmaker-manager → Running

**Verify StorageClass**
```bash
oc get storageclass
```

Expected:
```bash
 local-sc   kubernetes.io/no-provisioner   WaitForFirstConsumer
```

**Verify Disk Availability**
```bash
lsblk
```

Ensure:
- Disk is unused
- Disk is not mounted
- Disk has sufficient capacity


> **Note:**
> - Local Storage Operator creates only ONE PV per disk
>  - A used disk cannot create additional PVs
>  - Additional PVs require additional disks or partitions

**FIX:**

Add a disk by editing the existing LocalVolume. If a LocalVolume resource already exists (for example local-storage), you do not need to create a new one.
You can edit the existing LocalVolume and add the new disk.

**Edit the Existing LocalVolume**
```bash
kubectl edit localvolume local-storage -n openshift-local-storage
```
**Add the New Disk Under devicePaths**

Locate the storageClassDevices section and add the new disk path.

Before (example):
```bash
spec:
  storageClassDevices:
  - storageClassName: local-sc
    volumeMode: Filesystem
    fsType: xfs
    devicePaths:
    - /dev/nvme4n1
```

After (add one more disk):
```bash
spec:
  storageClassDevices:
  - storageClassName: local-sc
    volumeMode: Filesystem
    fsType: xfs
    devicePaths:
    - /dev/nvme4n1
    - /dev/nvme5n1
```

Save and exit the editor.

**Verify PV Creation**

Within a few seconds, the Local Storage Operator will create a new PV.
``'bash
oc get pv
```
Expected:
- One new PV per newly added disk

PVCs bind only after a new disk is detected

```bash
oc get pvc -A
```
Expected:
- STATUS: Bound

---

### 3. StatefulSet Pods Not Scheduling on SNO

StatefulSet pods (example: auth-apisix-etcd-0) remain Pending even though PV exists.

**Root Cause**

Local PVs are node-specific

Scheduler needs explicit node placement on SNO

**Fix** 

Patch the StatefulSet to pin it to the SNO node:
```bash
oc patch statefulset auth-apisix-etcd -n auth-apisix \
  --type='merge' \
  -p '{
    "spec": {
      "template": {
        "spec": {
          "nodeSelector": {
            "kubernetes.io/hostname": "<SNO_HOSTNAME>"
          }
        }
      }
    }
  }'
```

Restart the pod:
```bash
oc delete pod auth-apisix-etcd-0 -n auth-apisix
```
---

### 4. Route Exists but API Is Not Reachable
Checks:

```bash
oc get routes -A
oc describe route <route-name>
```
**Common Causes**

- Missing /etc/hosts entry
- Incorrect BASE_URL / cluster_url
- TLS mode mismatch
- DNS resolution failure

**Fix**

- Ensure hostname resolves correctly
- Verify TLS mode matches EI configuration
- Use curl -k only for debugging

---

### 5. Keycloak Token Generation Fails

Verify:
- Client ID exists
- Client secret is correct
- Access type is **Confidential**
- `KEYCLOAK_REALM` matches configuration
- Token endpoint URL is correct