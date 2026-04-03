# Enterprise Inference — Airgapped Deployment (Xeon + GenAI)

## Deployment Scope
- **Hardware**: Intel Xeon (CPU only, no Gaudi)
- **Active flags**: `deploy_kubernetes_fresh=on`, `deploy_ingress_controller=on`,
  `deploy_keycloak_apisix=on`, `deploy_genai_gateway=on`, `deploy_llm_models=on`
  — observability, ceph, istio, agenticai all OFF
- **Config entry point**: `core/inventory/inference-config.cfg`
- **Main deploy script**: `inference-stack-deploy.sh`

---

## Airgap Approach: JFrog Artifactory on VM1 as Mirror
VM1 IP: `100.67.152.212:8082` — VM2 pulls everything from JFrog instead of internet.

### JFrog Repos in Use
```
DOCKER
  ei-docker              local    fallback / manually pushed images
  ei-docker-dockerhub    remote   → registry-1.docker.io  (Langfuse, Bitnami, etcd)
  ei-docker-ecr          remote   → public.ecr.aws         (vLLM CPU)
  ei-docker-ghcr         remote   → ghcr.io                (TGI, TEI, LiteLLM)
  ei-docker-k8s          remote   → registry.k8s.io        (ingress-nginx controller) ← ADD
  ei-docker-virtual      virtual  aggregates all remotes + local

HELM
  ei-helm-local          local    Helm charts (HTTP upload via curl, NOT helm push OCI)
  ei-helm-ingress-nginx  remote   → kubernetes.github.io/ingress-nginx
  ei-helm-langfuse       remote   → langfuse.github.io/langfuse-k8s
  ei-helm-virtual        virtual  aggregates ei-helm-local + remotes

PYPI
  ei-pypi-local          local    manually uploaded wheels
  ei-pypi-remote         remote   → pypi.org
  ei-pypi-virtual        virtual  aggregates both

GENERIC
  ei-generic-binaries    local    kubectl, helm, yq, kubectx, kubens, kubespray, ansible collections
  ei-generic-models      local    Meta-Llama-3.1-8B-Instruct (~30 GB)
```

### Important: Helm Chart Upload Method
JFrog only supports **HelmOCI** package type (not plain Helm) — so `ei-helm-local` is HelmOCI type.
Charts are uploaded via **HTTP REST API** and `index.yaml` must be **manually generated and uploaded**.

```bash
# 1. Upload chart tarballs
curl -u admin:password -T ingress-nginx-4.12.2.tgz \
  "http://100.67.152.212:8082/artifactory/ei-helm-local/ingress-nginx-4.12.2.tgz"
curl -u admin:password -T langfuse-1.5.1.tgz \
  "http://100.67.152.212:8082/artifactory/ei-helm-local/langfuse-1.5.1.tgz"
curl -u admin:password -T apisix-2.8.1.tgz \
  "http://100.67.152.212:8082/artifactory/ei-helm-local/apisix-2.8.1.tgz"
curl -u admin:password -T keycloak-22.1.0.tgz \
  "http://100.67.152.212:8082/artifactory/ei-helm-local/keycloak-22.1.0.tgz"

# 2. Generate and upload index.yaml (REQUIRED — JFrog does not auto-generate it for HelmOCI)
mkdir ~/helm-charts-index
cp ingress-nginx-4.12.2.tgz langfuse-1.5.1.tgz apisix-2.8.1.tgz keycloak-22.1.0.tgz ~/helm-charts-index/
cd ~/helm-charts-index
helm repo index . --url http://100.67.152.212:8082/artifactory/ei-helm-local
curl -u admin:password -T index.yaml \
  "http://100.67.152.212:8082/artifactory/ei-helm-local/index.yaml"
```

**Validated** ✅ — all 4 charts served via `helm search repo ei-helm`:
```
ei-helm/apisix          2.8.1
ei-helm/ingress-nginx   4.12.2
ei-helm/keycloak        22.1.0
ei-helm/langfuse        1.5.1
```

**To add ei-helm-local as helm repo:**
```bash
helm repo add ei-helm http://100.67.152.212:8082/artifactory/ei-helm-local --force-update
helm repo update
```

---

## What Was Pre-loaded ✅
**Docker images**: vllm-cpu v0.10.2, tgi 2.4.0-intel-cpu, tei cpu-1.7, litellm v1.75.8,
bitnamilegacy/postgresql, bitnamilegacy/redis, bitnami/minio, ubuntu:22.04, Langfuse images (clickhouse, web, worker)

**Helm charts**: ingress-nginx 4.12.2, langfuse 1.5.1 (pushed as OCI — need re-upload via curl)

**PyPI**: ansible, ansible-core, attrs, cffi, cryptography, jinja2, jmespath, jsonschema,
markupsafe, netaddr, packaging, pycparser, pyyaml, referencing, resolvelib, rpds-py, typing-extensions

**Ansible collections**: community.kubernetes 2.0.1, community.general 12.5.0

**Binaries**: kubectl, helm, yq, kubectx, kubens, kubespray.tar.gz

**Model**: Meta-Llama-3.1-8B-Instruct (~30 GB)

---

## GAPS — What Is Still Missing

### 🔴 CRITICAL — Deployment fails without these

#### Docker Images
| Image | Needed By | Fix |
|---|---|---|
| `bitnamilegacy/etcd:3.5.10-debian-11-r2` | APISIX (`apisix-helm/values.yaml`) | `docker pull 100.67.152.212:8082/ei-docker-virtual/bitnamilegacy/etcd:3.5.10-debian-11-r2` |
| `bitnamilegacy/valkey:latest` | Langfuse cache | `docker pull 100.67.152.212:8082/ei-docker-virtual/bitnamilegacy/valkey:latest` |
| `bitnamilegacy/zookeeper:latest` | ClickHouse dep | `docker pull 100.67.152.212:8082/ei-docker-virtual/bitnamilegacy/zookeeper:latest` |
| ingress-nginx controller | Ingress | Add `ei-docker-k8s` remote → `registry.k8s.io` in JFrog, add to ei-docker-virtual |
| Keycloak image | Auth | Pulled via Keycloak Helm chart through ei-docker-dockerhub |

#### Helm Charts
| Chart | Version | Needed By | Fix |
|---|---|---|---|
| apisix | 2.8.1 | `apisix-helm/Chart.yaml` hard dependency | `helm pull apisix/apisix --version 2.8.1` → upload via curl to ei-helm-local |
| keycloak | latest | `deploy-keycloak-tls-cert.yml` | `helm pull bitnami/keycloak` → upload via curl to ei-helm-local |

#### PyPI Packages
`setup-bastion.yml` installs these separately from ansible — not in current upload:
| Package | Needed By |
|---|---|
| `kubernetes` | Every `kubernetes.core.k8s:` Ansible task across all playbooks |
| `jsonpatch` | Kubernetes patch operations |
| `requests` | HTTP calls in Ansible modules |
| `urllib3` | HTTP client dependency |

```bash
pip3 download kubernetes jsonpatch requests urllib3 -d ~/pip-wheels
twine upload --repository-url http://100.67.152.212:8082/artifactory/api/pypi/ei-pypi-local \
  -u admin -p password ~/pip-wheels/*.whl
```

#### Ansible Collections
`setup-bastion.yml` installs 4 collections — only 2 uploaded:
| Collection | Needed By |
|---|---|
| `kubernetes.core` | Every `kubernetes.core.k8s:` task — most critical missing item |
| `ansible.posix` | File/system tasks across playbooks |

```bash
ansible-galaxy collection download kubernetes.core --download-path ~/ansible-collections
ansible-galaxy collection download ansible.posix   --download-path ~/ansible-collections
curl -u admin:password -T kubernetes-core-*.tar.gz \
  "http://100.67.152.212:8082/artifactory/ei-generic-binaries/ansible-collections/kubernetes-core-latest.tar.gz"
curl -u admin:password -T ansible-posix-*.tar.gz \
  "http://100.67.152.212:8082/artifactory/ei-generic-binaries/ansible-collections/ansible-posix-latest.tar.gz"
```

#### Helm Charts: Re-upload via HTTP (not OCI)
ingress-nginx and langfuse were pushed via `helm push` (OCI) — must re-upload via curl so ei-helm-virtual can serve them over HTTP:
```bash
curl -u admin:password -T ingress-nginx-4.12.2.tgz \
  "http://100.67.152.212:8082/artifactory/ei-helm-local/ingress-nginx-4.12.2.tgz"
curl -u admin:password -T langfuse-1.5.1.tgz \
  "http://100.67.152.212:8082/artifactory/ei-helm-local/langfuse-1.5.1.tgz"
```

### 🟡 MEDIUM — Fails at specific steps
| Item | Issue | Fix |
|---|---|---|
| `get-helm-3` script | `setup-bastion.yml` line 132 curls `raw.githubusercontent.com` | Upload to `ei-generic-binaries`, patch playbook |
| `BAAI/bge-base-en-v1.5` | Required if TEI embeddings deployed | Download from HuggingFace, upload to `ei-generic-models` |
| apt packages (15+) | `setup-bastion.yml` runs `apt-get install` — no Debian mirror in JFrog | Add `ei-debian-ubuntu` remote + `ei-debian-virtual` in JFrog |

---

## EI Code Changes — Completed ✅

### Airgap variables added to `inference-config.cfg`
```
airgap_enabled=off        ← flip to on for VM2 airgap deployment
jfrog_url=http://100.67.152.212:8082/artifactory
jfrog_username=admin
jfrog_password=password
```

### Derived helm URL variables in `inference_common.yml`
```yaml
helm_repo_ingress_nginx: "{{ jfrog_url + '/ei-helm-virtual' if airgap_enabled | bool else 'https://kubernetes.github.io/ingress-nginx' }}"
helm_repo_langfuse:      "{{ jfrog_url + '/ei-helm-virtual' if airgap_enabled | bool else 'https://langfuse.github.io/langfuse-k8s' }}"
```

### Shell scripts — JFrog vars passed as --extra-vars

**`core/lib/components/ingress-controller.sh`**
```bash
# Before:
ansible-playbook ... --extra-vars "... ingress_controller=${ingress_controller}"
# After:
ansible-playbook ... --extra-vars "... ingress_controller=${ingress_controller} airgap_enabled=${airgap_enabled} jfrog_url=${jfrog_url} jfrog_username=${jfrog_username} jfrog_password=${jfrog_password}"
```

**`core/lib/components/keycloak-controller.sh`** — both playbook calls patched:
```bash
# run_keycloak_playbook:
ansible-playbook ... deploy-keycloak-controller.yml --extra-vars "airgap_enabled=${airgap_enabled} jfrog_url=${jfrog_url} jfrog_username=${jfrog_username} jfrog_password=${jfrog_password}"
# create_keycloak_tls_secret_playbook:
ansible-playbook ... deploy-keycloak-tls-cert.yml --extra-vars "... airgap_enabled=${airgap_enabled} jfrog_url=${jfrog_url} jfrog_username=${jfrog_username} jfrog_password=${jfrog_password}"
```

**`core/lib/components/genai-gateway-controller.sh`**
```bash
ansible-playbook ... --extra-vars "... airgap_enabled=${airgap_enabled} jfrog_url=${jfrog_url} jfrog_username=${jfrog_username} jfrog_password=${jfrog_password}"
```

### Playbooks — dual tasks (original URL kept, JFrog added with `when:`)

Pattern used in all 4 playbooks — original task kept with `when: not airgap_enabled`, new JFrog task added:
```yaml
- name: Add <repo> repository (internet)
  community.kubernetes.helm_repository:
    name: <repo>
    repo_url: https://<upstream-url>
    state: present
  when: not airgap_enabled | bool

- name: Add <repo> repository (airgap via JFrog)
  ansible.builtin.command: >
    helm repo add <repo> {{ helm_repo_<name> }}
    --username {{ jfrog_username }} --password {{ jfrog_password }}
    --force-update
  when: airgap_enabled | bool
  changed_when: false
```

| File | Repo |
|---|---|
| `core/playbooks/deploy-ingress-controller.yml` | ingress-nginx |
| `core/playbooks/deploy-keycloak-controller.yml` | ingress-nginx |
| `core/playbooks/deploy-keycloak-service.yml` | ingress-nginx |
| `core/playbooks/deploy-genai-gateway.yml` | langfuse |

### containerd mirror — `core/inventory/metadata/all.yml` ✅ WORKING
```yaml
containerd_registries_mirrors:
  - registry: "docker.io"
    prefix: "docker.io"
    mirrors:
      - host: "http://100.67.152.212:8082/v2/ei-docker-virtual"
        capabilities:
          - pull
          - resolve
        override_path: true
  - registry: "ghcr.io"
    prefix: "ghcr.io"
    mirrors:
      - host: "http://100.67.152.212:8082/v2/ei-docker-virtual"
        capabilities:
          - pull
          - resolve
        override_path: true
  - registry: "registry.k8s.io"
    prefix: "registry.k8s.io"
    mirrors:
      - host: "http://100.67.152.212:8082/v2/ei-docker-virtual"
        capabilities:
          - pull
          - resolve
        override_path: true
  - registry: "quay.io"
    prefix: "quay.io"
    mirrors:
      - host: "http://100.67.152.212:8082/v2/ei-docker-virtual"
        capabilities:
          - pull
          - resolve
        override_path: true
  - registry: "public.ecr.aws"
    prefix: "public.ecr.aws"
    mirrors:
      - host: "http://100.67.152.212:8082/v2/ei-docker-virtual"
        capabilities:
          - pull
          - resolve
        override_path: true
```

**Validated**: `docker.io/library/nginx:1.25.2-alpine` pulls through JFrog ✅ (confirmed by blocking Docker IP — pull still succeeded at LAN speed from JFrog)

**All docker.io images validated** ✅ — ubuntu, nginx, busybox, keycloak, postgresql, etcd, apisix all pulled through JFrog across multiple deployment runs.

**How to confirm an image pulled from JFrog (not internet):**
```bash
# Check bytes read in containerd log — bytes > 0 means downloaded, mirror was used
sudo journalctl -u containerd --no-pager | grep "stop pulling image docker.io" | grep -v "bytes read=0"

# Or check JFrog request log on VM1
tail -f /var/opt/jfrog/artifactory/log/request.log | grep <VM2-IP>
```

**How JFrog caching works:**
- `ei-docker-virtual` is a router only — nothing is stored there
- Images are cached in the underlying remote repo (`ei-docker-dockerhub`, `ei-docker-ghcr`, etc.)
- On first pull: JFrog fetches from internet and caches in the remote repo
- On subsequent pulls: JFrog serves from cache (no internet needed)
- Set remote repos to **Offline** in JFrog UI to enforce true airgap (serves cache only, refuses new fetches)

**Mirrors applied on VM2** (created manually after Kubespray run, until Kubespray template patch is in repo):
```bash
for reg in ghcr.io registry.k8s.io quay.io public.ecr.aws; do
  sudo mkdir -p /etc/containerd/certs.d/$reg
  sudo tee /etc/containerd/certs.d/$reg/hosts.toml <<EOF
server = "https://$reg"
[host."http://100.67.152.212:8082/v2/ei-docker-virtual"]
  capabilities = ["pull","resolve"]
  override_path = true
EOF
done
```

**JFrog remote repos needed per registry:**
| Registry | JFrog Remote Repo | Status |
|---|---|---|
| `docker.io` | `ei-docker-dockerhub` | ✅ Working |
| `ghcr.io` | `ei-docker-ghcr` | ✅ Exists, needs test |
| `public.ecr.aws` | `ei-docker-ecr` | ✅ Exists, needs test |
| `registry.k8s.io` | `ei-docker-k8s` | ✅ Created and validated |
| `quay.io` | `ei-docker-quay` | ✅ Created and validated |

**Critical rules — do NOT break these:**
- Mirror host MUST include `/v2/` before the repo name: `…/v2/ei-docker-virtual` not `…/ei-docker-virtual`
  - `override_path: true` makes containerd append the image path as-is, so `/v2/` must already be in the host URL
  - Without it JFrog gets `/ei-docker-virtual/library/nginx/…` → 404 HTML
- Do NOT set `skip_verify` (not even `skip_verify: false`) — any `skip_verify` field triggers containerd's HTTPS-first behavior
  - HTTPS fails (`tls: unrecognized name`), containerd falls back to docker.io, gets HTML, caches it as bad manifest blob
- JFrog auth flow: mirror returns 401 → containerd fetches Bearer token anonymously → retries → 200
  - JFrog anonymous access must be enabled with Read permission on `ei-docker` and `ei-docker-virtual`

### Kubespray hosts.toml template patch — `core/kubespray/roles/container-engine/containerd/templates/hosts.toml.j2` ✅
Kubespray's template unconditionally wrote `skip_verify = false` which broke HTTP mirrors. Patched to only write it when true:
```jinja2
{% if mirror.skip_verify | default(false) %}
  skip_verify = true
{% endif %}
```

### Recovering from the "HTML blob" corruption loop
If containerd caches an HTML 404 page as a manifest (sha256 `ea07845984…`), the CRI backoff loop re-caches it continuously. Full recovery:
```bash
# 1. Remove from CRI layer (stops backoff loop)
sudo crictl rmi docker.io/library/nginx:1.25.2-alpine 2>/dev/null; true
# 2. Remove from bolt DB
sudo ctr -n k8s.io images rm docker.io/library/nginx:1.25.2-alpine 2>/dev/null; true
# 3. Delete the blob file directly (ctr content rm leaves file on disk)
sudo rm -f /var/lib/containerd/io.containerd.content.v1.content/blobs/sha256/<bad-sha256>
# 4. Restart containerd
sudo systemctl restart containerd
```

### Direct JFrog pull hosts.toml — `/etc/containerd/certs.d/100.67.152.212:8082/hosts.toml`
For `ctr pull 100.67.152.212:8082/…` direct pulls (not mirror):
```toml
server = "http://100.67.152.212:8082"
[host."http://100.67.152.212:8082"]
  capabilities = ["pull", "resolve"]
  username = "admin"
  password = "password"
```
No `skip_verify` — it would force HTTPS-first and break HTTP JFrog.

---

## Next Steps (in order)
1. ✅ Add mirrors for ghcr.io, public.ecr.aws, registry.k8s.io, quay.io in `all.yml`
2. ✅ Create `ei-docker-k8s` remote → `registry.k8s.io` in JFrog UI, add to `ei-docker-virtual`
3. ✅ Create `ei-docker-quay` remote → `quay.io` in JFrog UI, add to `ei-docker-virtual`
4. ✅ Test registry.k8s.io and quay.io mirrors — both validated (pause:3.10, calico/node:v3.29.1)
5. ✅ Upload all Helm charts to ei-helm-local (ingress-nginx 4.12.2, langfuse 1.5.1, apisix 2.8.1, keycloak 22.1.0)
6. ✅ Generate and upload index.yaml manually — JFrog HelmOCI does not auto-generate it
7. ✅ Upload missing pip packages (kubernetes 35.0.0, jsonpatch 1.33, requests 2.33.1, urllib3 2.6.3 + all deps) to ei-pypi-local
8. ✅ Upload missing Ansible collections (ansible.posix 2.1.0) to ei-generic-binaries — kubernetes.core 6.3.0 was already there
9. ✅ Add Kubespray template patch to `core/roles/container-engine/containerd/templates/hosts.toml.j2` — auto-applied on every fresh deploy via `cp -r core/roles/* kubespray/roles/` in setup-env.sh
10. Set all JFrog remote repos to **Offline** to simulate true airgap
11. Set `airgap_enabled=on` in `inference-config.cfg` and run full deployment on VM2
12. Validate end-to-end with internet blocked

## Airgap Simulation — Block Internet on VM2
```bash
# Allow only VM1 (JFrog) + local traffic, block everything else
sudo iptables -A OUTPUT -m state --state ESTABLISHED,RELATED -j ACCEPT
sudo iptables -A OUTPUT -o lo -j ACCEPT
sudo iptables -A OUTPUT -d 100.67.152.212 -j ACCEPT
sudo iptables -A OUTPUT -d 10.0.0.0/8 -j ACCEPT
sudo iptables -A OUTPUT -d 192.168.0.0/16 -j ACCEPT
sudo iptables -A OUTPUT -j DROP

# To unblock
sudo iptables -D OUTPUT -m state --state ESTABLISHED,RELATED -j ACCEPT
sudo iptables -D OUTPUT -o lo -j ACCEPT
sudo iptables -D OUTPUT -d 100.67.152.212 -j ACCEPT
sudo iptables -D OUTPUT -d 10.0.0.0/8 -j ACCEPT
sudo iptables -D OUTPUT -d 192.168.0.0/16 -j ACCEPT
sudo iptables -D OUTPUT -j DROP
```
⚠️ Check `echo $SSH_CLIENT` before blocking — ensure your SSH source IP is in the allowed ranges or you will be locked out.
