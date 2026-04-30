# JFrog Setup for Enterprise Inference Airgapped Deployment

This guide walks you through setting up JFrog Artifactory on VM1 as a local mirror for
Enterprise Inference airgapped deployments. Once JFrog is set up, VM2 (the airgapped machine)
pulls all Docker images, Helm charts, Python packages, and binaries from JFrog instead of
the internet.

```
┌─────────────────────┐           ┌─────────────────────┐
│  VM1 (internet)     │  LAN      │  VM2 (airgapped)    │
│  JFrog Artifactory  │◄─────────►│  EI Deployment      │
│  :8082              │           │  Kubernetes + vLLM  │
│                     │           │                     │
│  - Docker images    │           │  No internet access │
│  - Helm charts      │           │  All pulls -> JFrog │
│  - Python packages  │           └─────────────────────┘
│  - Binaries         │
│  - LLM models       │
└─────────────────────┘
```

### Scripts in this folder

- **`jfrog-installation.sh`**: Installs all required tools and JFrog Artifactory on VM1
- **`jfrog-setup.sh`**: Creates repositories, enables access, and uploads all assets to JFrog

---

## Prerequisites

### System Requirements

This airgap solution requires two machines. Both machines must be on the same network and
must be able to reach each other over LAN. VM2 pulls all content from VM1 during deployment,
so connectivity between them is required throughout the entire process.

| Requirement | VM1 (JFrog machine) | VM2 (airgapped machine) |
|---|---|---|
| Purpose | Hosts JFrog Artifactory, downloads and stores all assets | Runs the Enterprise Inference stack (Kubernetes + vLLM) |
| Internet access | Required (to download Docker images, models, binaries) | Not required (blocked after initial setup) |
| Disk space | At least 80 GB free. This has been validated for downloading Llama-3.2-3B, Qwen3-0.6B, Qwen3-1.7B, and Qwen3-4B models. If you plan to download additional or larger models, you will need more disk space. | At least 80 GB free (for Kubernetes, container images, and model storage) |
| RAM | At least 8 GB | At least 64 GB (vLLM requires significant memory for CPU inference) |
| CPU | No special requirement (JFrog is a file server) | At least 16 cores recommended |
| Network | Must be reachable from VM2 on port 8082 | Must be reachable from VM1. **Internet access must be fully disabled before running the EI deployment.** EI will exit with an error if `airgap_enabled=yes` and the machine can still reach the internet. |
| OS | Ubuntu 22.04 LTS | Ubuntu 22.04 LTS |
| Access | Root or sudo privileges | Root or sudo privileges |

### Credentials required

Before you start, collect the following. Have all of them ready before running any scripts.

**JFrog License**

A license key is required to activate JFrog. Without it, JFrog will not serve any content.
If you already have a JFrog license, use that. If not, you can get a free 14-day trial at
https://jfrog.com/start-free/

1. Click 14-day free trial (not Platform Tour)
2. Select Self-Hosted
3. Fill in the registration form and click Confirm and Start
4. Check your email. JFrog will send you your username, password, and license key within a few minutes.
5. Copy the license key and keep it somewhere handy. You will need all three when completing the setup wizard in Step 2.

**HuggingFace Token**

Required to download LLM models. The following models are supported:

| Step | Model | Approximate size |
|---|---|---|
| 3i | meta-llama/Llama-3.2-3B-Instruct | ~6.5 GB |
| 3j | Qwen/Qwen3-0.6B | ~1.2 GB |
| 3k | Qwen/Qwen3-4B | ~7.6 GB |
| 3l | Qwen/Qwen3-1.7B | ~3.4 GB |

The Llama model is gated and requires you to accept the license agreement before downloading.
The Qwen models are open and do not require acceptance.

1. Accept the Llama 3.2 3B license at https://huggingface.co/meta-llama/Llama-3.2-3B-Instruct
2. Generate a token at https://huggingface.co/settings/tokens and select Read access.

**Docker Hub Credentials**

Required to pull one image (apache/apisix-ingress-controller) that cannot be fetched
through JFrog remote repos and must be pulled directly from Docker Hub.

Create a free account at https://hub.docker.com and generate a Personal Access Token at
https://hub.docker.com/settings/security. Use the token as your password when prompted.

---

## Step 1 - Install JFrog on VM1

VM1 must have internet access. Run the following on VM1.

First, install git:

```bash
sudo apt install -y git
```

Clone the repo and check out the airgap branch:

```bash
git clone https://github.com/cld2labs/Enterprise-Inference.git Enterprise-Inference
cd Enterprise-Inference
git checkout cld2labs/airgap
```

Then run the install script:

```bash
cd ~/Enterprise-Inference/third_party/Dell/air-gap/jfrog-setup
chmod +x jfrog-installation.sh
sudo ./jfrog-installation.sh
```

> During the install, the package manager may show a package configuration prompt. Press
> Enter or click OK to accept the defaults and continue.

The script installs these tools: curl, wget, git, jq, skopeo, helm, python3, pip3, ansible.

When the script finishes, JFrog is running at `http://localhost:8082`.

---

## Step 2 - Open the JFrog UI and Complete Setup

Open a browser on VM1 and go to `http://localhost:8082`.

If VM1 does not have a browser, set up an SSH tunnel from your local machine. Open a new
terminal window (not the one where you are already SSH'd into VM1) and run:

```bash
ssh -L 8082:localhost:8082 user@<VM1-IP> -N
```

> Leave that terminal open. Closing it will drop the tunnel and you will lose access to the
> JFrog UI.

Open `http://localhost:8082` in your local browser.

### First login and setup

When you open JFrog for the first time, it will walk you through a short setup wizard.

**1. Reset the default password**

Log in with the default credentials: admin / password

JFrog will immediately ask you to set a new password. Choose a password and save it. You
will need it when running `jfrog-setup.sh` in the next step.

**2. Activate the license**

JFrog will ask for a license key. Paste the trial license key from your email and click
Activate.

> JFrog will not serve any content until the license is activated. Do not skip this step.

**3. Set the base URL**

JFrog will ask for a base URL. Leave this blank and click Skip unless you have a specific
base URL. This is optional and does not affect the setup.

**4. Configure proxy**

Click Skip. A proxy is only needed if VM1 reaches the internet through a corporate proxy
server.

**5. Create repositories**

Click Skip. The `jfrog-setup.sh` script will create all required repositories automatically.

Click Finish to complete the wizard.

### Enable anonymous access (required manual step)

> [!IMPORTANT]
> This step must be done manually in the UI. The JFrog API cannot automate it reliably
> because it requires a token with a specific audience (`jfac@...`) that is not obtainable
> via the standard REST API. `jfrog-setup.sh` step 2 will warn about this and continue,
> but anonymous access will not be active until you complete this step.
>
> Without this, VM2 cannot pull Docker images through the containerd mirror.

1. In the JFrog UI, go to **Administration → Security → General**
2. Turn on **Allow Anonymous Access**
3. Click **Save**

You can verify it is working by running this on VM1 after the toggle is on:

```bash
curl -s "http://localhost:8082/v2/token?scope=repository%3Alibrary%2Fnginx%3Apull&service=localhost:8082" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print('OK' if d.get('token') else 'FAILED')"
```

If it prints `OK`, anonymous access is active and VM2 will be able to pull images.

---

## Step 3 - Create Repos, Enable Access, and Upload All Assets

### Run the full setup

Once the license is active, run the command below to start the setup. This will take a
while as it downloads and uploads all assets listed above.

> [!CAUTION]
> Run the script as a normal user, not with `sudo`. For example, run `./jfrog-setup.sh`,
> not `sudo ./jfrog-setup.sh`. Running as root breaks the SSH tunnel and the script will
> not be able to reach JFrog.

> [!NOTE]
> During step 3f, the script internally installs apt packages and will prompt for your
> sudo password. This is expected: enter your system password when prompted to continue.

```bash
cd ~/Enterprise-Inference/third_party/Dell/air-gap/jfrog-setup
chmod +x jfrog-setup.sh

# Replace VM1-IP with the actual value
./jfrog-setup.sh \
  --jfrog-url http://<VM1-IP>:8082/artifactory \
  --jfrog-user admin \
  --jfrog-pass <your-password> \
  --dockerhub-user <dockerhub-username> \
  --dockerhub-pass <dockerhub-pat> \
  --hf-token <hf-token>
```

### All available options

| Flag | Required | Description |
|---|---|---|
| `--jfrog-url URL` | Yes | JFrog base URL. Script fails to connect if not provided or incorrect |
| `--jfrog-user USER` | Yes | JFrog admin username. Script fails to authenticate if missing |
| `--jfrog-pass PASS` | Yes | JFrog admin password set during the UI wizard. Script fails to authenticate if missing |
| `--hf-token TOKEN` | Only for steps 3i, 3j, 3k | HuggingFace token with read access. Required for Llama-3.2-3B (gated) and Qwen models. If omitted, steps 3i, 3j, and 3k will be skipped with a warning |
| `--dockerhub-user USER` | Only for step 3a | Docker Hub username for `apache/apisix-ingress-controller`. If omitted, that image is skipped with a warning and all other images still upload |
| `--dockerhub-pass PASS` | Only for step 3a | Docker Hub password or Personal Access Token. Required alongside `--dockerhub-user` |
| `--step STEP` | No | Run only one specific step, e.g. `--step 3a`. Useful for re-running a failed step |
| `--skip STEP` | No | Skip a specific step. Can be repeated, e.g. `--skip 3i --skip 3j` to skip model uploads |
| `--workdir DIR` | No | Directory where files are downloaded before uploading to JFrog. Defaults to `/tmp/ei-airgap-upload` |
| `--dry-run` | No | Prints all commands without executing them. Useful for verifying what the script will do before running |

### Run one step at a time

If you want to run or re-run a specific step instead of the full script, use any of
these commands:

| Command | What it does |
|---|---|
| `./jfrog-setup.sh --step 1` | Creates all JFrog repositories: Docker repos for each upstream registry (Docker Hub, ECR, GHCR, registry.k8s.io, Quay), Helm, PyPI, Debian, and generic repos for binaries and models |
| `./jfrog-setup.sh --step 2` | Sets anonymous read permission targets on all Docker repos so VM2 can pull images without credentials. **Note**: the "Allow Anonymous Access" toggle in Administration → Security → General must be enabled manually in the UI before running this step — the JFrog API cannot automate that toggle |
| `./jfrog-setup.sh --step 3a` | Copies ~40 Docker images from upstream registries into JFrog using skopeo. Most images are pulled anonymously. `apache/apisix-ingress-controller:1.8.0` requires `--dockerhub-user` and `--dockerhub-pass` |
| `./jfrog-setup.sh --step 3b` | Downloads 10 Helm charts (ingress-nginx, langfuse, apisix, keycloak, postgresql, redis, clickhouse, minio, valkey, nri-resource-policy-balloons) and uploads them along with an `index.yaml` that JFrog does not generate automatically |
| `./jfrog-setup.sh --step 3c` | Downloads ~30 Python packages used by the EI deployment playbooks and uploads them to JFrog so VM2 can install them without internet access |
| `./jfrog-setup.sh --step 3d` | Uploads the pip installer wheel to JFrog. Required because Ubuntu disables pip by default and VM2 needs it to bootstrap the Python environment |
| `./jfrog-setup.sh --step 3e` | Downloads 4 Ansible collections used by the EI playbooks and uploads them to JFrog |
| `./jfrog-setup.sh --step 3f` | Downloads jq and its dependencies as .deb files and uploads them to JFrog. Also pre-caches all Kubespray apt packages (conntrack, socat, nfs-common, python3-pip, unzip, etc.) in JFrog by temporarily routing VM1's apt through JFrog. Uses `apt-get download` to force a network fetch for already-installed packages so JFrog caches them reliably. Prompts for sudo password during install |
| `./jfrog-setup.sh --step 3g` | Downloads all binaries Kubespray needs to set up the Kubernetes cluster (kubeadm, kubectl, kubelet, containerd, runc, etcd, calico, cni-plugins, crictl, helm, nerdctl, yq, kubectx, kubens) and uploads them to JFrog |
| `./jfrog-setup.sh --step 3h` | Packages the Kubespray repository as a tarball and uploads it to JFrog. VM2 uses this instead of cloning from GitHub |
| `./jfrog-setup.sh --step 3i --hf-token <hf-token>` | Downloads **meta-llama/Llama-3.2-3B-Instruct** (~6.5 GB) from HuggingFace and uploads all files to JFrog. Requires a HuggingFace token with access to the model |
| `./jfrog-setup.sh --step 3j --hf-token <hf-token>` | Downloads **Qwen/Qwen3-0.6B** (~1.2 GB) from HuggingFace and uploads all files to JFrog |
| `./jfrog-setup.sh --step 3k --hf-token <hf-token>` | Downloads **Qwen/Qwen3-4B** (~7.6 GB) from HuggingFace and uploads all files to JFrog |
| `./jfrog-setup.sh --step 3l --hf-token <hf-token>` | Downloads **Qwen/Qwen3-1.7B** (~3.4 GB) from HuggingFace and uploads all files to JFrog |
| `./jfrog-setup.sh --step 4` | Sets all remote repos to Offline so JFrog serves only cached content and does not fetch anything new from the internet. This enforces the true airgap |

---

## Summary

Once `jfrog-setup.sh` completes successfully, JFrog on VM1 is fully configured and ready
to serve as the sole package mirror for VM2. The following has been completed:

- All JFrog repositories created (Docker, Helm, PyPI, Debian, generic)
- Anonymous access enabled so VM2 can pull images without credentials
- All Docker images, Helm charts, Python packages, binaries, and LLM models uploaded
- All remote repos set to Offline: JFrog serves only cached content and will not fetch
  anything new from the internet

VM1 requires no further changes. Proceed to the [Enterprise Inference airgap deployment
guide](../EI/single-node/air-gap.md) to configure VM2 and run the EI stack.

---

## Troubleshooting

<details>
<summary>Click to expand</summary>

### Deployment exits with "airgap_enabled is set to yes but this machine has internet connectivity"

This check runs at the start of every EI deployment when `airgap_enabled=yes`. It means
VM2 can still reach the internet, which defeats the purpose of airgap mode — Docker images
not cached in JFrog would silently fall back to internet registries.

Disable internet access on VM2 before running the deployment. A common way to do this is
to drop the default route or use iptables:

```bash
# Option 1: remove the default route (re-add it later if needed)
sudo ip route del default

# Option 2: block outbound internet with iptables (allow LAN traffic to VM1)
sudo iptables -I OUTPUT -d <VM1-IP> -j ACCEPT
sudo iptables -I OUTPUT -d 0.0.0.0/0 -j DROP
```

After disabling internet, re-run the EI deployment. The check will pass once no internet
routes are reachable.

---

### Use skopeo to copy Docker images, not docker

Docker 29.x forces HTTPS even when insecure-registries is configured in
`/etc/docker/daemon.json`. Use skopeo instead as it handles HTTP correctly:

```bash
skopeo copy \
  --src-tls-verify=false \
  --dest-tls-verify=false \
  --dest-creds admin:<password> \
  docker://<upstream-registry>/<image>:<tag> \
  docker://<VM1-IP>:8082/ei-docker-local/<image>:<tag>
```

> Always push to `ei-docker-local`, not `ei-docker-virtual`. Virtual repos reject pushes.
> Images pushed to `ei-docker-local` are automatically served through `ei-docker-virtual`
> since local is a member of virtual.

### Verifying an image is cached

A plain curl request returns 404 even when an image is cached in JFrog. You need to
include Docker manifest Accept headers:

```bash
curl -s -u admin:<password> \
  -H "Accept: application/vnd.docker.distribution.manifest.v2+json" \
  -H "Accept: application/vnd.docker.distribution.manifest.list.v2+json" \
  -o /dev/null -w "%{http_code}" \
  "http://<VM1-IP>:8082/v2/ei-docker-virtual/library/nginx/manifests/1.25.2-alpine"
```

A response of 200 means the image is properly cached. Anything else means it is not.

### Very old image tags not available via Docker Hub

Docker Hub no longer serves very old tags (like busybox:1.28) through the v2 API, so
JFrog cannot proxy them. The workaround is to pull a newer working tag and push it under
the old tag name:

```bash
skopeo copy \
  --dest-tls-verify=false \
  --dest-creds admin:<password> \
  docker://<VM1-IP>:8082/ei-docker-virtual/library/busybox:latest \
  docker://<VM1-IP>:8082/ei-docker-local/library/busybox:1.28
```

### Anonymous access toggle in the UI does not fully work

The "Allow Anonymous Access" toggle in the JFrog UI only sets one of two required flags.
If VM2 cannot pull images without credentials, patch the config manually:

```bash
curl -su "admin:<password>" \
  "http://localhost:8082/artifactory/api/system/configuration" > /tmp/jfrog-config.xml

sed -i 's/<enabledForAnonymous>false<\/enabledForAnonymous>/<enabledForAnonymous>true<\/enabledForAnonymous>/' \
  /tmp/jfrog-config.xml

curl -su "admin:<password>" -X POST \
  "http://localhost:8082/artifactory/api/system/configuration" \
  -H "Content-Type: application/xml" \
  --data-binary @/tmp/jfrog-config.xml
```

> This is handled automatically by step 2 of `jfrog-setup.sh`. Only run this manually if
> VM2 is unable to pull images without credentials after the full setup.

### Virtual repos cannot be added to permission targets

If you try to add `ei-docker-virtual` to a JFrog permission target you will get an HTTP
400 error. Add the individual local and remote repos instead. Step 2 of `jfrog-setup.sh`
does this correctly.

### Helm index.yaml is not generated automatically

JFrog HelmOCI repos do not auto-generate `index.yaml`. After uploading chart tarballs,
generate and upload the index file manually:

```bash
mkdir ~/helm-index
cp *.tgz ~/helm-index
cd ~/helm-index
helm repo index . --url http://localhost:8082/artifactory/ei-helm-local
curl -u admin:<password> -T index.yaml \
  "http://localhost:8082/artifactory/ei-helm-local/index.yaml"
```

> Step 3b of `jfrog-setup.sh` does this automatically. Only run this manually if you are
> uploading charts outside of the script.

</details>
