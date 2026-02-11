# Troubleshooting Guide

This section provides common deployment and runtime issues observed during Intel® AI for Enterprise Inference setup — along with step-by-step resolutions.

**Issues:**
  1. [Missing Default User](#1-ansible-deployment-failure--missing-default-user)
  2. [Authorization or sudo Password Failure](#2-authorization-or-sudo-password-failure)
  3. [Configuration Mismatch (Wrong Parameters)](#3-configuration-mismatch-wrong-parameters)
  4. [Kubernetes Cluster Not Reachable](#4-kubernetes-cluster-not-reachable)
  5. [Habana Device Plugin CrashLoopBackOff](#5-habana-device-plugin-crashloopbackoff)
  6. [Model pods remain in "Pending" state](#6-model-pods-remain-in-pending-state)
  7. [Models' Output is Garbled and/or Model Pods Failing](#7-models-output-is-garbled-andor-model-pods-failing)
  8. [Model Deployment Failure with Padding-aware scheduling](#8-model-deployment-failure-with-padding-aware-scheduling)
  9. [Inference Stack Deploy Keycloak System Error](#9-inference-stack-deploy-keycloak-system-error)
  10. [Kubernetes pods failing with "disk pressure"](#10-kubernetes-pods-failing-with-disk-pressure)
  11. [Hugging face authentication failure](#11-Hugging-face-authentication-failure)
  12. [Docker Image Pull Failure](#12-Docker-Image-Pull-Failure)
  13. [Triton Package Compatibility Issue](#13-triton-package-compatibility-issue)
---

### 1. Ansible Deployment Failure — Missing Default User

TASK [download : Prep_download | Create staging directory on remote node]
fatal: [master1]: FAILED! => {"msg": "chown failed: failed to look up user ubuntu"}


**Cause:**

The default Ansible user "ubuntu" does not exist on your system.

**Fix:**

Many cloud images create the "ubuntu" user by default, but your system may not have it. Edit the inventory file to change the Ansible user name to your user:
```bash
vi inventory/hosts.yaml
```

Update the "ansible_user" with the user that owns Enterprise Inference, in the example below, just "user":

```bash
all:
  hosts:
    master1:
      ansible_connection: local
      ansible_user: user
      ansible_become: true
```

---

### 2. Authorization or sudo Password Failure

Deployment fails with authorization or privilege escalation issues.

**Fix:**

Two options:
1. every time, just prior to executing inference-stack-deploy.sh, execute "sudo echo sudoing" and enter your sudo password. This normally will keep your sudo authorization in effect through the execution of inference-stack-deploy.sh.
2. Add `--ask-become-pass` parameter in the inference-stack-deploy.sh script. Specifically, append this flag after `--become-user=root` in the `ansible-playbook` command of `run_reset_playbook()` and `run_fresh_install_playbook()` (lines 821 and 865). NOTE that this will mean the script will wait for input of your sudo password each time it is run.

---

### 3. Configuration Mismatch (Wrong Parameters)

Deployment fails due to incorrect or missing configuration values.

**Fix:**
Before re-running deployment, verify and update your inference-config.cfg. These values must match your actual deployment environment.
```bash
cluster_url=api.example.com  # <-- Replace with cluster url
cert_file=~/certs/cert.pem
key_file=~/certs/key.pem
keycloak_client_id=my-client-id   # <-- Replace with your Keycloak client ID
keycloak_admin_user=your-keycloak-admin-user   # <-- Replace with your keycloak admin username
keycloak_admin_password=changeme   # <-- Replace with your keycloak admin password
vault_pass_code=place-holder-123
deploy_kubernetes_fresh=on
deploy_ingress_controller=on
deploy_keycloak_apisix=on
deploy_genai_gateway=off
deploy_observability=off
deploy_llm_models=on
deploy_ceph=off
deploy_istio=off
```

---

### 4. Kubernetes Cluster Not Reachable

Deployment shows “cluster not reachable” or kubectl command failures.

**Possible Causes & Fixes:**

  - **Cause:** Sudo authorization is not cached
  
  - **Fix:** Prior to executing inference-stack-deploy.sh, execute any sudo command, such as `sudo echo sudoing`. That will cache your credentials for the time that inference-stack-deploy.sh is executing.

  - **Cause:** Ansible was uninstalled

  - **Fix:** Reinstall manually:

```bash
sudo apt update
sudo apt install -y ansible
```

  - **Cause:** Kubernetes configuration mismatch

  - **Fix:** Ensure `~/.kube/config` exists and the context points to the correct cluster.

  - **Cause:** Sudo is stripping the kubectl path from the environment, so kubectl is not found.

  - **Fix:** Ensure that the sudoers file includes the path `/usr/local/bin` in the `secure_path` variable. See the user-guide prerequisites for details.

---

### 5. Habana Device Plugin CrashLoopBackOff

habana-ai-device-plugin-ds-*  CrashLoopBackOff
ERROR: failed detecting Habana's devices on the system: get device name: no habana devices on the system

**Cause:**
Device plugin unable to detect Gaudi3 PCIe cards.

**Fix:**
Update your Habana device plugin version. Version 1.22.1-6 is recommended.

kubectl set image pod/habana-ai-device-plugin-ds-tjbch \
  habana-ai-device-plugin=vault.habana.ai/docker-k8s-device-plugin/docker-k8s-device-plugin:1.22.1-6

**Verification:**

```bash
kubectl get pods -A
```

Note: Ensure the habana-ai-device-plugin status changes to Running.

Check driver/NIC versions	hl-smi
Confirm runtime version	`dpkg -l
Validate Kubernetes health	kubectl get nodes -o wide
Check device plugin logs	kubectl logs -n habana-ai-operator <device-plugin-pod>

---

### 6. Model Pods Remain in "Pending" State

Problem: After the inference stack is deployed, model pods remain in the "Pending" state and do not progress to the "Running" state, as shown here:

```bash
user@master1:~/Enterprise-Inference/core$ kubectl get pods
NAME                                          READY   STATUS    RESTARTS   AGE
keycloak-0                                    1/1     Running   0          15m
keycloak-postgresql-0                         1/1     Running   0          15m
vllm-deepkseek-r1-qwen-32b-64b885895f-dh566   0/1     Pending   0          10m
vllm-llama-8b-786d7678ff-6fr6l                0/1     Pending   0          10m
```

This can occur if the habana-ai-operator pod does not identify that the gaudi3 devices are allocatable. To check if this is the reason, execute the following command:

```bash
kubectl describe node master1
```

Look for the the "Capacity" and "Allocatable" sections as below, and ensure that both list the correct number of habana.ai/gaudi3 devices for your hardware.

```bash
Capacity:
  habana.ai/gaudi:    8
Allocatable:
  habana.ai/gaudi:    8
```

If the "Allocatable" section shows zero (0), your pods will remain in the pending state.
To resolve this, execute the following command to restart the operator so it registers the devices:

```bash
kubectl rollout restart ds habana-ai-device-plugin-ds -n habana-ai-operator
```

If the "rollout restart" does not resolve the issue, a system restart often works to fix it.

---

### 7. Models' Output is Garbled and/or Model Pods Failing

IOMMU passthrough is required for Gaudi 3 on **Ubuntu 24.04.2/22.04.5 with Linux kernel 6.8**, and models can produce garbled output or fail if this setting is not applied. Skip this section if a different OS or kernel version is used.

To enable IOMMU passthrough:
1. Add `GRUB_CMDLINE_LINUX_DEFAULT="iommu=pt intel_iommu=on"` to `/etc/default/grub`.
2. Run sudo update-grub.
3. Reboot the system.

---

### 8. Model Deployment Failure with Padding-aware scheduling

**Error:** Padding-aware scheduling currently does not work with chunked prefill

**Casue:** This issue occurs when the --use-padding-aware-scheduling flag is enabled while deploying a vLLM model on Habana Gaudi3.
The current vLLM version (v0.9.0.1+Gaudi-1.22.0) does not support using padding-aware scheduling together with chunked prefill.

**Fix:** If your workload doesn’t require padding-aware scheduling, you can disable it to allow deployment to proceed.

Edit your `gaudi3-values.yaml` file. Locate and remove the following flag from the vLLM startup command:
```bash
--use-padding-aware-scheduling
```

Redeploy the vLLM Helm chart:
```bash
helm upgrade --install vllm-llama-8b ./core/helm-charts/vllm \
  --values ./core/helm-charts/vllm/gaudi3-values.yaml
```

Confirm the pod starts successfully:
```bash
kubectl get pods
kubectl logs -f <vllm-pod-name>
```

---

### 9. Inference Stack Deploy Keycloak System Error

**Error:** TASK \[Deploy Keycloak System\] FAILED! ...  "Failure when executing Helm command ... response status code 429: toomanyrequests: You have reached your unauthenticated pull rate limit."

**Cause:** This error was seen when attempting a redeployment (running inference_stack_deploy.sh, menu "1) Provision Enterprise Inference Cluster") when the Keycloak service is already installed and the inference_config.cfg "deploy_keycloak_apisix"="on".

**Fix:** Update inference_config.cfg to change "deploy_keycloak_apisix=on" to "deploy_keycloak_apisix=off" and rerun inference_stack_deploy.sh.

---

### 10. Kubernetes pods failing with "disk pressure"

If pods are hanging in "pending" state or in CrashLoopBackoff with "disk pressure" messages when examining logs (kubectl logs <pod> or kubectl describe pod <pod>), you may be lacking space on a required filesystem. The Enterprise Inference standard installation will use /opt/local-path-provisioner for model local storage. Ensure this location has sufficient space allocated. It is recommended that you undeploy any failing models, allocate more space to the local-path-provisioner, then redeploy your models.

---

### 11. Hugging face authentication failure

**Error :** Deployment fails or hangs when running inference-stack-deploy.sh or while deploying models with below error

```bash
su "${USERNAME}" -c "cd /home/${USERNAME}/Enterprise-Inference/core && echo -e '1\n${MODELS}\nyes' | bash ./inference-stack-deploy.sh --models '${MODELS}' --cpu-or-gpu '${GPU_TYPE}' --hugging-face-token ${HUGGINGFACE_TOKEN}" resolution to this is getting new hygging face and updating in inference-config
```
**Cause:** The Hugging Face token passed via --hugging-face-token does not match the token stored in inference-config.cfg, or the token has expired / been revoked.

**Fix:** 

1. Check if hugging face token has required permission for model trying to deploy.
2. Check if hugging face token is expired. generate new hugging face token, Update your inference-config.cfg and run inference

---

### 12. Docker Image Pull Failure

**Error:** During deployment, the image download task fails and retries multiple times:
```bash
TASK [download : Download_container | Download image if required]
FAILED - RETRYING: [master1]: Download_container | Download image if required
```

**Cause**: Docker Hub enforces pull rate limits for unauthenticated users.
When multiple images are pulled during Enterprise Inference deployment, the limit may be exceeded, causing HTTP 429 Too Many Requests.

This commonly occurs when:

Re-running deployments multiple times

Deploying on fresh nodes without Docker authentication

Multiple images are pulled in quick succession

**Fix:** 

Verify the issue with a manual pull test
```bash
sudo ctr -n k8s.io images pull docker.io/library/registry:2.8.1
```

If this fails with 429 Too Many Requests, Docker Hub rate limiting is confirmed.

**Option A — Authenticate to Docker Hub**

-> Log in to Docker Hub so containerd can pull images with higher limits.
```bash
sudo docker login
```
-> Enter your Docker Hub username and password (or access token).

-> After login, retry the image pull:
```bash
sudo ctr -n k8s.io images pull docker.io/kubernetesui/metrics-scraper:v1.0.8
```

**Option B — Wait for Rate Limit Reset**

Docker Hub rate limits typically reset after a few hours. wait 2–4 hours and retry deployment or image pull

### 13. Triton Package Compatibility Issue

**Error:**
During model deployment, the inference service may fail to start and worker processes may exit unexpectedly with an error similar to:

> RuntimeError: Worker failed with error *module `triton` has no attribute `next_power_of_2`*.

**Cause:**
This issue is caused by a compatibility mismatch between the Triton package and the vLLM execution path used during model deployment. It commonly occurs when deploying models using vLLM with default parameter, when Triton is present but does not fully support the required execution path, or when deployments target CPU or accelerator-based platforms (including Gaudi) without platform-specific tuning. As a result, 
vLLM workers fail during initialization and the inference engine does not reach a ready state.

**Fix:**
Apply the Intel-recommended environment variables and command-line parameters during model deployment to ensure vLLM uses a compatible execution path.

**Environment Variables (YAML):**
```yaml
VLLM_CPU_KVCACHE_SPACE: "40"
VLLM_RPC_TIMEOUT: "100000"
VLLM_ALLOW_LONG_MAX_MODEL_LEN: "1"
VLLM_ENGINE_ITERATION_TIMEOUT_S: "120"
VLLM_CPU_NUM_OF_RESERVED_CPU: "0"
VLLM_CPU_SGL_KERNEL: "1"
HF_HUB_DISABLE_XET: "1"
```

**Extra Command Arguments (YAML list):**
```yaml
- "--block-size"
- "128"
- "--dtype"
- "bfloat16"
- "--distributed_executor_backend"
- "mp"
- "--enable_chunked_prefill"
- "--enforce-eager"
- "--max-model-len"
- "33024"
- "--max-num-batched-tokens"
- "2048"
- "--max-num-seqs"
- "256"
```

**Notes:**
Tensor parallelism and pipeline parallelism are determined dynamically based on the deployment configuration:

```yaml
tensor_parallel_size: "{{ .Values.tensor_parallel_size }}"
pipeline_parallel_size: "{{ .Values.pipeline_parallel_size }}"
```

**Result:**
After applying the recommended parameters, model deployment completes successfully and the inference service starts without worker initialization failures.

