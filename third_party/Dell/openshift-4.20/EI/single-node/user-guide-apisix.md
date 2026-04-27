# Intel® AI for Enterprise Inference - OpenShift (APISIX)
## Red Hat OpenShift Brownfield Deployment (Single Node OpenShift – SNO)

This guide is a **supplement** to the [OpenShift Brownfield Deployment Guide](../../../../../docs/brownfield/brownfield_deployment_openshift.md).

Follow that guide end-to-end and refer to the sections below for SNO and APISIX-specific steps not covered there.

---

## SNO-Specific Requirements

The brownfield guide targets a generic OpenShift cluster. For SNO, these additional requirements apply:

| Component | Requirement |
|-----------|-------------|
| OpenShift Container Platform | v4.20.0 |
| Kubernetes Version | v1.33.6 |
| Node Type | Single Node OpenShift (SNO) |
| Operating System | Red Hat CoreOS (RHCOS) |
| StorageClass | local-sc |
| Local Storage Operator | installed and bound |
| TLS | Edge termination (Router-managed) |

The inference stack must be deployed from a **separate machine**, not the SNO node itself.

| Component | Requirement |
|-----------|-------------|
| Deployment Machine | Ubuntu 22.04 |
| Enterprise Inference Version | release-1.4.0 |
| Accelerator | CPU / Gaudi3 |
| Network | Full egress (Registry + Hugging Face) |

---

## Additional Pre-Deployment Steps

### Copy kubeconfig to the Deployment Machine

The brownfield guide assumes kubeconfig is already on the deployment machine. For SNO, copy it from your local machine first:

```bash
scp PATH_TO_YOUR_KUBECONFIG_FILE username@<VM2_IP>:/home/user/admin.kubeconfig
```

Then follow [Prepare Kubeconfig](../../../../../docs/brownfield/brownfield_deployment.md#prepare-kubeconfig) to complete the setup.

### DNS Resolution (If No Corporate DNS)

SNO exposes additional routes not mentioned in the brownfield guide. Add these entries to `/etc/hosts` on the deployment machine:

```bash
sudo vi /etc/hosts
```
```
<SNO_IP> api.<cluster>.<domain>
<SNO_IP> keycloak-okd.apps.<cluster>.<domain>
<SNO_IP> okd.apps.<cluster>.<domain>
```

> If enterprise DNS is configured correctly, this step is not required.

### Activate Virtual Environment

```bash
cd ~/Enterprise-Inference/core/kubespray
source venv/bin/activate
pip install kubernetes
```

### Create Certificate Files

```bash
mkdir -p ~/certs && \
openssl req -x509 -nodes -days 365 \
-newkey rsa:2048 \
-keyout ~/certs/ei.key \
-out ~/certs/ei.crt \
-subj "/CN=okd.apps.<CLUSTER>.<DOMAIN>"
```
---

### Update Inference Configuration

When updating `core/inventory/inference-config.cfg` per the brownfield guide, apply these APISIX-specific values:

> **Note:**
> - Replace `<CLUSTER>.<DOMAIN>` with your SNO cluster URL
> - Set `cpu_or_gpu` to `cpu` for Xeon models or `gaudi3` for Intel Gaudi 3
> - Set Keycloak values: `keycloak_client_id`, `keycloak_admin_user`, `keycloak_admin_password`
> - Replace `hugging_face_token` with your Hugging Face token
> - `deploy_kubernetes_fresh=off` and `deploy_ingress_controller=off` are required for brownfield

```
cluster_url=okd.apps.<CLUSTER>.<DOMAIN>
cert_file=~/certs/ei.crt
key_file=~/certs/ei.key
keycloak_client_id=my-client-id
keycloak_admin_user=your-keycloak-admin-user
keycloak_admin_password=changeme
hugging_face_token=your_hugging_face_token
hugging_face_token_falcon3=your_hugging_face_token
cpu_or_gpu=gaudi3
deploy_kubernetes_fresh=off
deploy_ingress_controller=off
deploy_keycloak_apisix=on
deploy_genai_gateway=off
```

### Update hosts.yaml

```bash
cp -f docs/examples/single-node/hosts.yaml core/inventory/hosts.yaml
```

> The `ansible_user` field defaults to `ubuntu`. Change it to the actual username if different.

---

## Running the Deployment (SNO-Specific)

The brownfield guide runs `./inference-stack-deploy.sh` directly. On SNO, `sudo` is required and does not inherit environment variables — export `KUBECONFIG` explicitly before running:

**Gaudi**
```bash
cd core
chmod +x inference-stack-deploy.sh
export KUBECONFIG=/home/user/.kube/config
sudo -E ./inference-stack-deploy.sh --models "1"
```

**CPU**
```bash
cd core
chmod +x inference-stack-deploy.sh
export KUBECONFIG=/home/user/.kube/config
sudo -E ./inference-stack-deploy.sh --models "21" --cpu-or-gpu "cpu"
```

When prompted, choose **4) Brownfield Deployment**, provide the kubeconfig path (e.g. `~/.kube/config`), then select **1) Initial deployment**.

> See the [full list of available model IDs](../../../ubuntu-22.04/iac/README.md#pre-integrated-models-list).

---

## Verify the Deployment

In addition to the route verification in the brownfield guide, run these APISIX-specific checks:

**Verify Namespaces**
```bash
kubectl get ns | egrep "auth-apisix|default"
```
Expected: `default`, `auth-apisix`

**Verify Pods**
```bash
kubectl get pods -A
```
Expected: all pods `Running`, no `CrashLoopBackOff` or `Pending`.

**Health Check**
```bash
kubectl get pv
kubectl get pvc -A
kubectl get routes -A
```
Expected: PV = `Bound`, PVC = `Bound`, Routes created.

---

## Test the Inference

### Obtain Access Token

Ensure Keycloak values in `core/scripts/generate-token.sh` match those in `core/inventory/inference-config.cfg`.

> Replace `BASE_URL` with `https://okd.apps.CLUSTER-NAME.DOMAIN-NAME` wherever required.

```bash
cd Enterprise-Inference/core/scripts
chmod +x generate-token.sh
. generate-token.sh
```

Confirm the token is set:
```bash
echo $BASE_URL
echo $TOKEN
```

If a valid token is returned (long JWT string), the environment is ready for inference testing.

### Run a Test Query

**Gaudi:**
```bash
curl -k https://${BASE_URL}/Llama-3.1-8B-Instruct/v1/completions \
-X POST \
-d '{"model": "meta-llama/Llama-3.1-8B-Instruct", "prompt": "What is Deep Learning?", "max_tokens": 25, "temperature": 0}' \
-H 'Content-Type: application/json' \
-H "Authorization: Bearer $TOKEN"
```

**CPU:**
```bash
curl -k ${BASE_URL}/Llama-3.1-8B-Instruct-vllmcpu/v1/completions \
-X POST \
-d '{"model": "meta-llama/Llama-3.1-8B-Instruct", "prompt": "What is Deep Learning?", "max_tokens": 25, "temperature": 0}' \
-H 'Content-Type: application/json' \
-H "Authorization: Bearer $TOKEN"
```

If successful, the model will return a completion response.

---

## Troubleshooting

- [SNO Troubleshooting Guide](./troubleshooting.md)
