# Troubleshooting Guide

This section provides common deployment and runtime issues observed during Intel® AI for Enterprise Inference setup — along with step-by-step resolutions.

**Issues:**
  1. [Missing Default User](#1-ansible-deployment-failure--missing-default-user)
  2. [Configuration Mismatch (Wrong Parameters)](#2-configuration-mismatch-wrong-parameters)
  3. [Kubernetes Cluster Not Reachable](#3-kubernetes-cluster-not-reachable)
  4. [Failed to create Keycloak Client](#4-failed-to-create-keycloak-client)
  5. [Selinux module not found error](#5-selinux-module-not-found-error)
     
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

Update the "ansible_user" with the user that owns Enterprise Inference, in the example below, just "vpcuser":

```bash
all:
  hosts:
    master1:
      ansible_connection: local
      ansible_user: vpcuser
      ansible_become: true
```

---


### 2. Configuration Mismatch (Wrong Parameters)

Deployment fails due to incorrect or missing configuration values.

**Fix:**
Before re-running deployment, verify and update your inference-config.cfg:

```bash
cluster_url=api.example.com
cert_file=~/certs/cert.pem
key_file=~/certs/key.pem
keycloak_client_id=my-client-id
keycloak_admin_user=your-keycloak-admin-user
keycloak_admin_password=changeme
hugging_face_token=your_hugging_face_token
hugging_face_token_falcon3=your_hugging_face_token
models=
cpu_or_gpu=gaudi3
vault_pass_code=place-holder-123
deploy_kubernetes_fresh=on
deploy_ingress_controller=on
deploy_observability=off
deploy_llm_models=on
deploy_ceph=off
deploy_istio=off
uninstall_ceph=off

```

---

### 3. Kubernetes Cluster Not Reachable

Deployment shows “cluster not reachable” or kubectl command failures.

**Possible Causes & Fixes:**

  - **Cause:** Sudo authorization is not cached
  
  - **Fix:** Prior to executing inference-stack-deploy.sh, execute any sudo command, such as `sudo echo sudoing`. That will cache your credentials for the time that inference-stack-deploy.sh is executing.

  - **Cause:** Ansible was uninstalled

  - **Fix:** Reinstall manually:

```bash
sudo dnf install -y ansible-core
```

  - **Cause:** Kubernetes configuration mismatch

  - **Fix:** Ensure `~/.kube/config` exists and the context points to the correct cluster.

  - **Cause:** Sudo is stripping the kubectl path from the environment, so kubectl is not found.

  - **Fix:** Ensure that the sudoers file includes the path `/usr/local/bin` in the `secure_path` variable. See the user-guide prerequisites for details.

---



### 4. Failed to create Keycloak Client

**Error2:** 
FAILED! => {"changed": true, "cmd": ["/tmp/helm-charts/keycloak-realmcreation.sh", "api.example.com", "api-admin", "changeme!!", "api"], "delta": "0:00:00.104837", "end": "2025-11-24 21:15:26.098248", "msg": "non-zero return code", "rc": 1, "start": "2025-11-24 21:15:25.993411", "stderr": "", "stderr_lines": [], "stdout": "Logged in successfully\nFailed to create client: {\"error\":\"unknown_error\",\"error_description\":\"For more on this error consult the server log at the debug level.\"}", "stdout_lines": ["Logged in successfully", "Failed to create client: {\"error\":\"unknown_error\",\"error_description\":\"For more on this error consult the server log at the debug level.\"}"]}

**Fix:**

Run below commands, where "vpcuser" is your application owner:

```bash
cd /home/vpcuser/Enterprise-Inference/core/scripts
chmod +x keycloak-realmcreation.sh
./keycloak-realmcreation.sh api.example.com api-admin "changeme!!" api
```
---


### 5. Selinux module not found error
**Error:** FAILED! => {"changed": false, "msg": "Failed to import the required Python library (libselinux-python) on master1's Python /usr/bin/python3. Please read the module documentation and install it in the appropriate location. If the required library is installed, but Ansible is using the wrong Python interpreter, please consult the documentation on ansible_python_interpreter"}

**Fix:**

Run this below command:
```bash
sudo dnf install -y python3-libselinux || sudo yum install -y python3-libselinux
```
Also, add below line in _hosts.yml_
```bash
 ansible_python_interpreter: /usr/libexec/platform-python
 ```
