# Prerequisites for Setting Up Intel® AI for Enterprise Inference

   - [System Requirement](#system-requirement)   
   - [SSH Key Setup](#ssh-key-setup)
   - [Network and Storage Requirement](#network-and-storage-requirement)
   - [DNS and SSL/TLS Setup](#dns-and-ssltls-setup)
     - [Production Environment](#production-environment)
     - [Development Environment](#development-environment)
  - [Hugging Face Token Generation](#hugging-face-token-generation)

The first step is to get access to the hardware platforms. This guide assumes the user can log in to all nodes. 


#### System Requirements:

| Category            | Details                                                                                                           |
|---------------------|-------------------------------------------------------------------------------------------------------------------|
| Operating System    | Ubuntu 22.04                                                                                                |
| Hardware Platforms  | 4th Gen Intel® Xeon® Scalable processors<br>5th Gen Intel® Xeon® Scalable processors<br>6th Gen Intel® Xeon® Scalable processors<br>3rd Gen Intel® Xeon® Scalable processors and Intel® Gaudi® 2 AI Accelerator<br>4th Gen Intel® Xeon® Scalable processors and Intel® Gaudi® 2 AI Accelerator <br>6th Gen Intel® Xeon® Scalable processors and Intel® Gaudi® 3 AI Accelerator|
| Gaudi Firmware Version | 1.20.0 or newer

>**Note**: For Intel® Gaudi AI Accelerators, there are additional steps to ensure the node(s) meet the requirements. Follow the [Gaudi prerequisites guide](./gaudi-prerequisites.md) before proceeding. For Intel® Xeon® Scalable processors, no additional setup is needed.

All steps need to be completed before deploying Enterprise Inference. By the end of the prerequisites, the following artifacts should be ready:
1. SSH key pair
2. SSL/TLS certificate files
3. Hugging Face token 

## SSH Key Setup

Log in as a **non-root** user with sudo privileges to set up an SSH key with enable passwordless SSH. Using `root` or a user with a password may lead to unexpected behavior during deployment.

1. Generate an SSH key pair using the `ssh-keygen` command. Otherwise, an existing key pair can be used.

    Open any console terminal on a laptop or server and run this command: 
    ```bash
    ssh-keygen -t rsa -b 4096
    ```
    Give a name to the key if desired, and leave the password blank.

2. Copy the public key (i.e. `id_rsa.pub`) to all the control plane and workload nodes that will be part of the cluster.

3. On each node, add the contents of the public key to `.ssh/authorized_keys` of the user account used to connect to the nodes. The command below can be used to do so.
    
    ```bash
    echo "<the_PUBLIC_KEY_CONTENTS>" >> ~/.ssh/authorized_keys
    ```

4. Ensure that the SSH service is running and enabled on all the nodes. Verify all nodes can be logged in to using the private SSH key (i.e. `id_rsa`) or password-based authentication from the Ansible control machine. This can be done with these commands:

    ```bash
    chmod 600 <path_to_PRIVATE_KEY>
    ssh -i <path_to_PRIVATE_KEY> <USERNAME>@<IP_ADDRESS>
    ```

    If a bastion host is used for secure access to the cluster nodes, configure the bastion host with the necessary SSH keys or authentication methods, and ensure that the Ansible control machine can connect to the cluster nodes through the bastion host.


## Network and Storage Requirement

### Network Requirement
- Configure a network topology that allows communication between the control plane nodes and workload nodes.
- Ensure that the nodes have internet access to pull the required Docker images and other dependencies during the deployment process.
- Ensure that the necessary ports are open for communication (e.g., ports for Kubernetes API server, etcd, etc.).

### Storage Requirement
When planning for storage, it is important to consider both the needs of the cluster and the applications you intend to deploy:
- Attach sufficient storage to the nodes based on the specific requirements and design of the cluster.
- For model deployment, allocate storage based on the size of the models you plan to deploy. Larger models may require more storage space.
- If deploying observability tools, it is recommended to allocate at least 30GB of storage for optimal performance.   


## DNS and SSL/TLS Setup

### Production Environment

#### DNS Setup
- Use a registered domain name and configure its DNS records to point to your production server or load balancer.

#### SSL/TLS Setup
- Obtain an SSL/TLS certificate from a trusted Certificate Authority (CA).
- Install the certificate on your production system following standard procedures.
- Ensure your infrastructure supports automatic renewal or set up a reminder to renew certificates before expiry.

#### Notes
- Use a reliable DNS provider and trusted CA to ensure secure and stable access.
- Open required firewall ports (e.g., 80 for HTTP validation) if needed during certificate issuance.
    
### Development Environment
For this setup, `api.example.com` will be used as the DNS and mapped to `localhost` to test locally.

Modify `/etc/hosts` by adding this line to map the DNS to `127.0.0.1` or `localhost`. Alternatively, the DNS can be mapped to the private IP address of the machine. Run *hostname -I* to acquire the private IP address.
```bash
127.0.0.1 api.example.com
```

Generate a self-signed SSL certificate with OpenSSL. For this example, `api.example.com` is used as the DNS.
```bash
mkdir -p ~/certs && cd ~/certs
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes -subj "/CN=api.example.com"
```

This generates two files:
- `cert.pem`: The self-signed certificate.
- `key.pem`: The private key.


## Hugging Face Token Generation
1. Go to the [Hugging Face website](https://huggingface.co/) and sign in or create a new account.
2. Generate a [user access token](https://huggingface.co/docs/transformers.js/en/guides/private#step-1-generating-a-user-access-token). Write down the value of the token in some place safe.

## Istio

Istio is an open-source service mesh platform that provides a way to manage, secure, and observe microservices in a distributed application architecture, particularly in Kubernetes environments. Refer [Istio Documentation](https://istio.io/latest/docs/) for more information on Istio.

Configure `inference-config.cfg` file to add `deploy_istio=on` option to install Istio.

To verify mutual TLS refer [Verify mutual TLS](https://istio.io/latest/docs/ambient/usage/verify-mtls-enabled/).


## Ceph Storage Filesystem
Ceph is a distributed storage system that provides file, block and object storage and is deployed in large scale production clusters. For mode informaton refer [Rook Ceph Documentation](https://rook.io/docs/rook/latest/Getting-Started/intro/) 

### Ceph Prerequisites

To configure the Ceph storage cluster, ensure that at least one of the following local storage types is available:

- **Raw devices** (no partitions or formatted filesystems)
- **Raw partitions** (no formatted filesystem)
- **LVM Logical Volumes** (no formatted filesystem)
- **Persistent Volumes** available from a storage class in block mode

To check if your devices or partitions are formatted with filesystems, use the following command:

```bash
lsblk -f
```

Example output:
```
NAME                  FSTYPE      LABEL UUID                                   MOUNTPOINT
vda
└─vda1                LVM2_member       >eSO50t-GkUV-YKTH-WsGq-hNJY-eKNf-3i07IB
    ├─ubuntu--vg-root   ext4              c2366f76-6e21-4f10-a8f3-6776212e2fe4   /
    └─ubuntu--vg-swap_1 swap              9492a3dc-ad75-47cd-9596-678e8cf17ff9   [SWAP]
vdb
```

If the FSTYPE field is not empty, there is a filesystem on top of the corresponding device. In this example, vdb is available to Rook, while vda and its partitions have a filesystem and are not available.

Configure `inference-config.cfg` file to add `deploy_ceph=on` option to enable ceph storage clutser setup.

Configure `inventory/hosts.yaml` file to add the avialable device under the required hosts. Refer the below example where vdb and vdc devices are added to `master1.

```yaml
all:
  hosts:
    master1:
      devices: [vdb, vdc]
      ansible_connection: local
      ansible_user: ubuntu
      ansible_become: true
  children:
    kube_control_plane:
      hosts:
        master1:
    kube_node:
      hosts:
        master1:
    etcd:
      hosts:
        master1:
    k8s_cluster:
      children:
        kube_control_plane:
        kube_node:
    calico_rr:
      hosts: {}
```

### Uninstall Ceph Cluster

⚠️ **Warning**: Uninstalling the Ceph cluster will permanently erase all Ceph data. Any workloads using Ceph storage will be disrupted and may require redeployment after removal.

To uninstall the Ceph storage cluster:

1. Set `uninstall_ceph=on` in the `inference-config.cfg` file to uninstall the Ceph storage cluster setup.

2. This option will permanently delete all Ceph data by:
   - Removing all Ceph storage pools and filesystems
   - Deleting all persistent volume claims
   - Uninstalling Rook-Ceph operator and cluster
   - Removing all Ceph-related CRDs
   - Deleting local storage data (`/var/lib/rook`)

3. **Format storage devices if required:**
   ```bash
   # Replace <device> with your actual storage device (e.g., /dev/vdb)
   sudo wipefs -a /dev/<device>
   sudo sgdisk --zap-all /dev/<device>
   sudo dd if=/dev/zero of=/dev/<device> bs=1M count=100 status=progress
   ```

   **Important**: Always verify the device name before running these commands to avoid data loss.

## Troubleshooting

  ### Ceph Storage Cluster Setup

  If Ceph OSDs skip devices due to GPT headers or existing filesystems, clean the device before use. Replace `<device>` with your actual device name (e.g., `/dev/vdb`):

  ```bash
  sudo sgdisk --zap-all <device>
  sudo wipefs -a <device>
  ```

  Repeat for each device as needed. **Always verify the device name to avoid data loss.**

  ### Istio CNI Error: File Descriptor Limit

  Increase file descriptor and inotify limits with the following commands:

  ```bash
  ulimit -n 262144
  sudo sysctl -w fs.inotify.max_user_watches=1048576
  sudo sysctl -w fs.inotify.max_user_instances=8192
  sudo sysctl -w fs.inotify.max_queued_events=32768
  ```

  **Note:** Adjust these values based on your system requirements.
  
## Next Steps
After completing the prerequisites, proceed to the [Deployment Options](./README.md#deployment-options) section of the guide to set up Enterprise Inference.
