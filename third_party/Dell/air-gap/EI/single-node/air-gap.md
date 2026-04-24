# Airgapped Deployment Guide

This document is a continuation of the [JFrog Setup README](../../jfrog-setup/README.md).

It assumes JFrog Artifactory is already installed on VM1, all repositories are created, and all assets (Docker images, Helm charts, PyPI packages, binaries, and the LLM model) have been uploaded. If you have not done that yet, complete the JFrog setup first.

## Architecture

```
VM1 (internet-connected)          VM2 (airgapped)
┌─────────────────────┐           ┌─────────────────────┐
│  JFrog Artifactory  │◄──LAN────►│  EI Deployment      │
│  :8082              │           │  Kubernetes + vLLM  │
│  - Docker images    │           │                     │
│  - Helm charts      │           │  No internet access │
│  - PyPI packages    │           │  All pulls → JFrog  │
│  - Binaries         │           └─────────────────────┘
│  - LLM models       │
└─────────────────────┘
```

---

## Step 1 - Block Internet on VM2

Before deploying, verify and then block internet access on VM2. All traffic must go through JFrog on VM1.

### Check current internet access

```bash
curl -s --max-time 5 https://google.com && echo "HAS INTERNET" || echo "NO INTERNET"
curl -s --max-time 5 https://huggingface.co && echo "HAS INTERNET" || echo "NO INTERNET"
```

### Block internet (allow only LAN and loopback)

Before running the iptables rules, find your LAN subnet and SSH client subnet:

```bash
# Your VM2 IP - the first two octets give you the LAN subnet
hostname -I
# Example output: 100.67.177.224  --> LAN subnet is 100.67.0.0/16

# Your SSH client IP - use the first three octets as the subnet
echo $SSH_CLIENT
# Example output: 100.64.29.169 40047 22  --> SSH client subnet is 100.64.29.0/24
```

Use those values in the rules below. The rules must be added one at a time in order -- each step inserts at a specific position, so do not skip any.

Replace `<LAN-SUBNET>` with the first two octets of VM2's IP followed by `.0.0` (for example, if VM2 is `100.67.177.224`, use `100.67.0.0`).

Replace `<SSH-CLIENT-SUBNET>` with the first three octets of the SSH client IP followed by `.0` (for example, if the client IP is `100.64.29.169`, use `100.64.29.0`).

**Step 1 -- Install iptables-persistent before blocking internet.**
Once the DROP rule is active, apt-get cannot reach the Ubuntu mirror. Install the package first while internet is still open.

```bash
sudo apt-get -o Acquire::ForceIPv4=true install -y iptables-persistent
```

Note: the `-o Acquire::ForceIPv4=true` flag is needed because Ubuntu mirrors advertise IPv6 addresses. Without it, apt may try IPv6 first and hang.

**Step 2 -- Apply the iptables rules.**

```bash
sudo iptables -F OUTPUT
sudo iptables -I OUTPUT 1 -m state --state ESTABLISHED,RELATED -j ACCEPT
sudo iptables -I OUTPUT 2 -o lo -j ACCEPT
sudo iptables -I OUTPUT 3 -d 127.0.0.0/8 -j ACCEPT
sudo iptables -I OUTPUT 4 -d 10.0.0.0/8 -j ACCEPT
sudo iptables -I OUTPUT 5 -d <LAN-SUBNET>/16 -j ACCEPT
sudo iptables -I OUTPUT 6 -d <SSH-CLIENT-SUBNET>/24 -j ACCEPT
sudo iptables -I OUTPUT 7 -d 192.168.0.0/16 -j ACCEPT
sudo iptables -A OUTPUT -j DROP
```

**Step 3 -- Save the rules so they survive a reboot.**

```bash
sudo netfilter-persistent save
```

If `iptables-persistent` is not available on your system (for example, the Ubuntu mirror is unreachable), save the rules manually instead:

```bash
sudo mkdir -p /etc/iptables
sudo iptables-save | sudo tee /etc/iptables/rules.v4

sudo tee /etc/network/if-pre-up.d/iptables-restore > /dev/null << 'EOF'
#!/bin/sh
iptables-restore < /etc/iptables/rules.v4
EOF
sudo chmod +x /etc/network/if-pre-up.d/iptables-restore
```

### Verify airgap

```bash
curl -s --max-time 5 https://google.com && echo "FAIL - internet still open" || echo "OK - internet blocked"
curl -s --max-time 5 http://<VM1-IP>:8082/artifactory/api/system/ping && echo "OK - JFrog reachable" || echo "FAIL - JFrog unreachable"
```

---

## Step 2 - Copy the Enterprise Inference Repo to VM2

From a machine with access to both the repo and VM2, clone the repository and check out the airgap branch:

```bash
git clone https://github.com/cld2labs/Enterprise-Inference.git
cd Enterprise-Inference
git checkout ei/airgapped
```

Then copy it to VM2:

```bash
scp -r ~/Enterprise-Inference user@<VM2-IP>:~/
```

Or copy via USB or shared storage if the environment is fully disconnected.

After copying, log in to VM2 and strip Windows CRLF line endings (required if the files were edited on a Windows machine):

```bash
find ~/Enterprise-Inference -name "*.sh" -o -name "*.yml" -o -name "*.yaml" -o -name "*.cfg" | \
  xargs sed -i 's/\r//'
```

---

## Step 3 - Configure `inference-config.cfg`

```bash
vi ~/Enterprise-Inference/core/inventory/inference-config.cfg
```

Set the following values. Replace each placeholder with your actual values:

```
cluster_url=api.example.com
cert_file=~/certs/cert.pem
key_file=~/certs/key.pem
keycloak_client_id=my-client-id
keycloak_admin_user=your-keycloak-admin-user
keycloak_admin_password=changeme
hugging_face_token=<your-huggingface-token>     # Replace with your HuggingFace token
hugging_face_token_falcon3=<your-huggingface-token>   # Replace with your HuggingFace token
models=
cpu_or_gpu=cpu
vault_pass_code=place-holder-123
deploy_kubernetes_fresh=on
deploy_ingress_controller=on
deploy_keycloak_apisix=on
deploy_genai_gateway=off
deploy_observability=off
deploy_llm_models=on
deploy_ceph=off
deploy_istio=off
uninstall_ceph=off
deploy_nri_balloon_policy=no

# ---------------------------------------------------------------------------
# Airgap Configuration
# Set airgap_enabled=on to route all pulls through JFrog on VM1.
# ---------------------------------------------------------------------------
airgap_enabled=on
jfrog_url=http://<VM1-IP>:8082/artifactory
jfrog_username=admin
jfrog_password=<your-jfrog-password>
```

Replace the following placeholders with your own values before running the deployment:

| Placeholder | What to replace with |
|---|---|
| `<VM1-IP>` | IP address of VM1 (the JFrog machine) |
| `<your-jfrog-password>` | JFrog admin password set during the UI wizard in Step 2 |
| `<your-huggingface-token>` | Your HuggingFace token with read access to the gated Llama models |

### Apply single-node inventory

```bash
cp ~/Enterprise-Inference/docs/examples/single-node/hosts.yaml \
   ~/Enterprise-Inference/core/inventory/hosts.yaml
```

Then update `ansible_user` to match the deployment user:

```bash
sed -i -E "/^[[:space:]]*master1:/,/^[[:space:]]{2}children:/ \
  s/^([[:space:]]*ansible_user:[[:space:]]*).*/\1$(whoami)/" \
  ~/Enterprise-Inference/core/inventory/hosts.yaml
```

### Generate SSL certificates

```bash
mkdir -p ~/certs
openssl req -x509 -newkey rsa:4096 \
  -keyout ~/certs/key.pem \
  -out ~/certs/cert.pem \
  -days 365 -nodes \
  -subj '/CN=api.example.com'
```

These paths are referenced in `inference-config.cfg` as `cert_file` and `key_file`.

### Add VM2 hosts entry for `api.example.com`

```bash
echo "$(hostname -I | awk '{print $1}') api.example.com" | sudo tee -a /etc/hosts
```

---

## Step 4 - Run the Deployment

```bash
cd ~/Enterprise-Inference/core
chmod +x inference-stack-deploy.sh
./inference-stack-deploy.sh
```

The deployment will:
1. Install prerequisites (pip from JFrog PyPI, Ansible collections from JFrog)
2. Download Kubespray from JFrog
3. Deploy Kubernetes via Kubespray (all binaries and images from JFrog)
4. Deploy ingress-nginx, Keycloak, APISIX
5. Deploy vLLM model pods

### Monitor deployment

```bash
# Watch pods come up
kubectl get pods -w

# Check vLLM pod logs (model loading)
kubectl logs <vllm-pod-name> --tail=20 | grep -v "OMP tid"
```

Expected pod states when complete:

```
keycloak-0                    1/1 Running
keycloak-postgresql-0         1/1 Running
vllm-llama-8b-cpu-*           1/1 Running
```

---

## Step 5 - Test Inference

### Generate Keycloak token

```bash
cd ~/Enterprise-Inference/core
. scripts/generate-token.sh
```

### Verify models are available

```bash
curl -s http://api.example.com:32353/Llama-3.1-8B-Instruct-vllmcpu/v1/models \
  -H "Authorization: Bearer $TOKEN" | jq .
```

### Test inference

```bash
curl -k https://${BASE_URL}/Llama-3.1-8B-Instruct-vllmcpu/v1/completions \
  -X POST \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "model": "meta-llama/Llama-3.1-8B-Instruct",
    "prompt": "What is Deep Learning?",
    "max_tokens": 25,
    "temperature": 0
  }'
```

---

For troubleshooting common failures, see [air-gap-troubleshooting.md](air-gap-troubleshooting.md).
