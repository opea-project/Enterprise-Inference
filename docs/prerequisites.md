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
| Gaudi Firmware Version | 1.20.0

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


## Next Steps
After completing the prerequisites, proceed to the [Deployment Options](./README.md#deployment-options) section of the guide to set up Enterprise Inference.
