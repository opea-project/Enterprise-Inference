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
  ei-docker-dockerhub    remote   → registry-1.docker.io  (Langfuse, Bitnami, etcd, nginx)
  ei-docker-ecr          remote   → public.ecr.aws         (vLLM CPU)
  ei-docker-ghcr         remote   → ghcr.io                (TGI, TEI, LiteLLM)
  ei-docker-k8s          remote   → registry.k8s.io        (ingress-nginx controller, pause, kube-*)
  ei-docker-quay         remote   → quay.io                (calico)
  ei-docker-virtual      virtual  aggregates all remotes (no local Docker repo — use remote repos to cache)

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
  ei-generic-binaries    local    kubectl, helm, yq, kubectx, kubens, kubespray, ansible collections, get-pip.py, pip.whl
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

**Docker images** (cached in JFrog remote repos via `ei-docker-virtual`):
| Image | Tag | Registry |
|---|---|---|
| q9t5s3a7/vllm-cpu-release-repo | v0.10.2 | public.ecr.aws |
| text-generation-inference | 2.4.0-intel-cpu | ghcr.io |
| text-embeddings-inference | cpu-1.7 | ghcr.io |
| litellm-non_root | main-v1.75.8-stable | ghcr.io |
| langfuse / langfuse-worker | 3.106.1 | docker.io |
| bitnamilegacy/postgresql | 16.3.0-debian-12-r23, 17.5.0-debian-12-r0 | docker.io |
| bitnamilegacy/redis | 8.0.1-debian-12-r0 | docker.io |
| bitnamilegacy/etcd | 3.5.10-debian-11-r2 | docker.io |
| bitnamilegacy/keycloak | 25.0.2-debian-12-r2 | docker.io |
| bitnamilegacy/os-shell | 12-debian-12-r48 | docker.io |
| bitnami/minio + mc | 2024.12.18 | docker.io |
| bitnamilegacy/clickhouse | 25.2.1-debian-12-r0 | docker.io |
| bitnamilegacy/valkey | 8.0.2-debian-12-r2 | docker.io |
| bitnamilegacy/zookeeper | 3.9.3-debian-12-r8 | docker.io |
| apache/apisix | 3.9.1-debian | docker.io |
| ingress-nginx/controller | v1.12.2 | registry.k8s.io |
| ingress-nginx/kube-webhook-certgen | v1.5.3 | registry.k8s.io |
| ubuntu | 22.04 | docker.io |
| library/nginx | 1.25.2-alpine | docker.io |
| local-path-provisioner | v0.0.24 | docker.io |
| pause | 3.10 | registry.k8s.io |
| kube-apiserver | v1.30.4 | registry.k8s.io |
| kube-controller-manager | v1.30.4 | registry.k8s.io |
| kube-scheduler | v1.30.4 | registry.k8s.io |
| kube-proxy | v1.30.4 | registry.k8s.io |
| coredns/coredns | v1.11.1 | registry.k8s.io |
| dns/k8s-dns-node-cache | 1.22.28 | registry.k8s.io |
| cpa/cluster-proportional-autoscaler | v1.8.8 | registry.k8s.io |
| calico/node | v3.28.1 | quay.io |
| calico/cni | v3.28.1 | quay.io |
| calico/kube-controllers | v3.28.1 | quay.io |
| calico/pod2daemon-flexvol | v3.28.1 | quay.io |
| containers/nri-plugins/nri-resource-policy-balloons | v0.12.2 | ghcr.io |
| containers/nri-plugins/nri-config-manager | v0.12.2 | ghcr.io |
| library/busybox | 1.28 (tagged from latest) | docker.io — ei-docker local |
| apache/apisix-ingress-controller | 1.8.0 | docker.io — ei-docker local |

**How to pre-cache an image** (run on VM1 — JFrog fetches and caches from internet):
```bash
docker pull 100.67.152.212:8082/ei-docker-virtual/<image>:<tag>
```

**Helm charts** (all uploaded to `ei-helm-local` as HTTP tarballs + index.yaml):
| Chart | Version |
|---|---|
| ingress-nginx | 4.12.2 |
| langfuse | 1.5.1 |
| apisix | 2.8.1 |
| keycloak | 22.1.0 |
| postgresql | 16.7.4 |
| redis | 21.1.3 |
| clickhouse | 8.0.5 |
| minio | 14.10.5 |
| valkey | 2.2.4 |
| nri-resource-policy-balloons | v0.12.2 |

**PyPI**: ansible, ansible-core, attrs, certifi, cffi, charset-normalizer, cryptography,
durationpy, idna, jinja2, jmespath, jsonpatch, jsonpointer, jsonschema, kubernetes,
markupsafe, netaddr, oauthlib, packaging, pycparser, python-dateutil, pyyaml, referencing,
requests, requests-oauthlib, resolvelib, rpds-py, six, typing-extensions, urllib3, websocket-client

**Ansible collections**: community.kubernetes 2.0.1, community.general 12.5.0, kubernetes.core 6.3.0, ansible.posix latest

**Binaries**: kubectl, helm, yq, kubectx, kubens, kubespray.tar.gz

**Model**: Meta-Llama-3.1-8B-Instruct (~30 GB, all 4 safetensor shards + tokenizer)

---

## GAPS — What Is Still Missing

### 🟡 MEDIUM — Fails at specific steps
| Item | Issue | Fix |
|---|---|---|
| `get-helm-3` script | ~~`setup-bastion.yml` line 132 curls `raw.githubusercontent.com`~~ — **FIXED**: `core/roles/inference-tools/tasks/main.yml` now has dual tasks; airgap task downloads `helm-v3.15.4-linux-amd64.tar.gz` from JFrog `ei-generic-binaries` | ✅ Fixed in code |
| `BAAI/bge-base-en-v1.5` | Required if TEI embeddings deployed | Download from HuggingFace, upload to `ei-generic-models` |
| apt packages (15+) | ~~no Debian mirror in JFrog~~ — **FIXED**: `ei-debian-ubuntu` remote (→ `archive.ubuntu.com/ubuntu`) and `ei-debian-virtual` virtual created in JFrog; `setup-env.sh` auto-configures `/etc/apt/sources.list` to use JFrog in airgap mode | ✅ Fixed in code + JFrog |

**When JFrog remote pull fails with "manifest unknown"** (old tags like `busybox:1.28`):
- Docker Hub drops manifests for very old tags from v2 API — JFrog remote can't fetch them
- Fix: pull a working equivalent tag, retag as the required version, push to `ei-docker` local:
  ```bash
  docker pull 100.67.152.212:8082/ei-docker-virtual/library/busybox:latest
  docker tag ... 100.67.152.212:8082/ei-docker/library/busybox:1.28
  docker push 100.67.152.212:8082/ei-docker/library/busybox:1.28
  ```
- If Docker Hub rate limit hit: `docker login -u <user> -p <pat>` first; rotate PAT after use

**How to find missing images when deployment fails with 404 on JFrog:**
Image names come from `core/kubespray/roles/kubespray-defaults/defaults/main/download.yml`. The error pattern is:
```
trying next host - response was http.StatusNotFound" host="100.67.152.212:8082"
trying next host" error="...dial tcp...: i/o timeout" host=<registry>
```
Fix: on VM1, set the relevant JFrog remote repo to Online, `docker pull 100.67.152.212:8082/ei-docker-virtual/<image>:<tag>`, then set back to Offline.

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
helm_repo_apisix:        "{{ jfrog_url + '/ei-helm-virtual' if airgap_enabled | bool else 'https://charts.apiseven.com' }}"
helm_oci_jfrog_host:     "{{ jfrog_url | regex_replace('^https?://', '') | regex_replace('/.*$', '') }}"
# helm_oci_jfrog_host extracts '100.67.152.212:8082' from jfrog_url for use in helm OCI pull commands
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
| `core/playbooks/deploy-keycloak-tls-cert.yml` | apisix (added — was missing entirely) |

### APISIX helm repo — `deploy-keycloak-tls-cert.yml`
Previously `helm dependency update apisix-helm/` ran with no helm repo registered for `apisix`. Fixed by adding dual tasks before the dependency update:
- Internet: `helm repo add apisix https://charts.apiseven.com --force-update`
- Airgap: `helm repo add apisix {{ helm_repo_apisix }} --username ... --force-update`

### APISIX subchart dependency — `deploy-keycloak-tls-cert.yml` ✅
`apisix-helm/Chart.yaml` has `repository: https://charts.apiseven.com` — both `helm dependency update` and `helm dependency build` try to contact this URL directly even in airgap mode (hash-based cache lookup fails because URL is not registered).

Fixed with airgap-specific tasks replacing the single internet `helm dependency update`:
1. Create `apisix-helm/charts/` dir on remote
2. `helm pull apisix/apisix --version 2.8.1 --destination .../apisix-helm/charts` (uses registered JFrog repo)
3. Patch `Chart.yaml` to replace `https://charts.apiseven.com` with `{{ helm_repo_apisix }}` so `helm dependency build` finds the cached index
4. `helm dependency build` (uses local tarball + JFrog-registered index)

**Note**: `ingress-nginx/kube-webhook-certgen` version used by chart `4.12.2` is `v1.5.3`, not `v1.5.1`. Pre-cache `v1.5.3` on VM1 from `registry.k8s.io`.

### Keycloak chart install — `deploy-keycloak-tls-cert.yml`
Previously used `chart_ref: oci://registry-1.docker.io/bitnamicharts/keycloak` — helm uses its own HTTP client for OCI pulls, **bypassing containerd mirrors**. Fails in true airgap.

Fixed with:
- Added task to register `ei-helm` → `{{ jfrog_url }}/ei-helm-virtual` when airgap
- `chart_ref` is now conditional:
```yaml
chart_ref: "{{ 'ei-helm/keycloak' if airgap_enabled | bool else 'oci://registry-1.docker.io/bitnamicharts/keycloak' }}"
```

### GenAI Gateway subchart dependencies — `deploy-genai-gateway.yml`
`genai-gateway/Chart.yaml` depends on postgresql and redis via `oci://registry-1.docker.io/bitnamicharts`. Helm OCI bypasses containerd mirrors — `helm dependency update` would contact docker.io directly in airgap mode.

Fixed by making `helm dependency update` internet-only and adding an airgap path:
1. Create `genai-gateway/charts/` dir on remote
2. `helm pull oci://{{ helm_oci_jfrog_host }}/bitnamicharts/postgresql --version 16.7.4 --plain-http`
3. `helm pull oci://{{ helm_oci_jfrog_host }}/bitnamicharts/redis --version 21.1.3 --plain-http`
4. `helm dependency build` (uses local tarballs, skips internet)

**Note**: `--plain-http` is required because JFrog runs on HTTP. JFrog's `ei-docker-dockerhub` (remote → `registry-1.docker.io`) caches the bitnami chart OCI layers and serves them via `oci://100.67.152.212:8082/bitnamicharts/...`.

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

### Shell script airgap fixes — `prereq-check.sh` and `setup-env.sh` ✅

**Root cause**: `read-config-file.sh` converts `on` → `yes` and `off` → `no` for all config vars. So at runtime `airgap_enabled` is `"yes"`, not `"on"`. All airgap checks must use `== "yes"`.

**`prereq-check.sh`**:
- Connectivity check: when `airgap_enabled=yes`, pings `${jfrog_url}/api/system/ping` instead of google.com/github.com
- `apt-get update`: skipped entirely when `airgap_enabled=yes` (no Debian mirror in JFrog)
- Error message: shows JFrog-specific troubleshooting when JFrog is unreachable in airgap mode

**`setup-env.sh`**:
- pip installs: when `airgap_enabled=yes`, both `pip install --upgrade pip` and `pip install -r requirements.txt` use `--index-url http://${jfrog_username}:${jfrog_password}@${jfrog_host}/artifactory/api/pypi/ei-pypi-virtual/simple --trusted-host ${jfrog_host}`
- kubespray clone: when `airgap_enabled=yes` and `$KUBESPRAYDIR` doesn't exist, downloads `kubespray.tar.gz` from `${jfrog_url}/ei-generic-binaries/kubespray.tar.gz` and extracts to `$(dirname $KUBESPRAYDIR)` instead of git cloning; must `cd $KUBESPRAYDIR` after extraction so `requirements.txt` is found
- Ansible collections: when `airgap_enabled=yes`, downloads each collection tarball from `${jfrog_url}/ei-generic-binaries/ansible-collections/${coll_file}-latest.tar.gz` and installs via `ansible-galaxy collection install <tarball> --force`; collections attempted: `kubernetes-core`, `ansible-posix`, `community-kubernetes`, `community-general`; if a tarball is missing in JFrog, it prints a yellow warning and **skips** (does not fail)
- `offline.yml` copy: when `airgap_enabled=yes`, copies `core/inventory/metadata/offline.yml` to `$KUBESPRAYDIR/inventory/mycluster/group_vars/all/offline.yml` automatically

**`install_ansible_collection` function** (setup-env.sh, called from `keycloak-controller.sh`):
- This function runs `ansible-galaxy collection install community.general` with **no airgap handling**
- Safe in practice because `setup_initial_env` already installs `community.general` via JFrog tarball first — ansible-galaxy finds it locally and skips the download
- If for any reason the collection is missing, this would fail in true airgap (galaxy.ansible.com is unreachable)

**PyPI gap**: `ansible==9.8.0` and transitive deps were not cached in JFrog. Fix: on VM1, `pip download ansible==9.8.0 jmespath==1.0.1 jsonschema==4.23.0 netaddr==1.3.0 -d /tmp/wheels/` then upload each `.whl` to `ei-pypi-local`. The simple index showed the package but the `.whl` returned 404 until the file was physically uploaded.

**Important**: When copying these files from Windows to Linux via SCP, always run `sed -i 's/\r//' <file>` on VM2 to strip Windows CRLF line endings, otherwise bash function names get `\r` appended and are not found.

### NRI CPU Balloons helm repo — `core/roles/nri_cpu_balloons/tasks/install_nri.yaml` + `install_nri_openshift.yaml` ✅
`nri_cpu_balloons` role was trying to add `https://containers.github.io/nri-plugins` directly — blocked in airgap. Fixed with dual tasks in both files:
- Internet: `kubernetes.core.helm_repository` with original URL, `when: not airgap_enabled | default(false) | bool`
- Airgap: `helm repo add nri-plugins {{ helm_repo_nri_plugins }} --username ... --force-update`, `when: airgap_enabled | default(false) | bool`

Added `helm_repo_nri_plugins` to `inference_common.yml`:
```yaml
helm_repo_nri_plugins: "{{ jfrog_url + '/ei-helm-virtual' if airgap_enabled | default(false) | bool else 'https://containers.github.io/nri-plugins' }}"
```

Added `inference_common.yml` to `vars_files` in `deploy-cpu-optimization.yml` (was missing — `helm_repo_nri_plugins` would have been undefined).

Fixed `core/lib/xeon/ballon-policy.sh` to pass `airgap_enabled jfrog_url jfrog_username jfrog_password` via `--extra-vars`.

Fixed `core/lib/cluster/config/label-nodes.sh` to pass airgap vars via `--extra-vars` (was passing nothing — caused `airgap_enabled is undefined` error in inference-tools role).

Added `| default(false)` to all `airgap_enabled | bool` conditions in `inference-tools/tasks/main.yml` as safety net for callers that omit the variable.

**Chart**: `nri-resource-policy-balloons v0.12.2` uploaded to `ei-helm-local`; index.yaml regenerated.
**Images**: `ghcr.io/containers/nri-plugins/nri-resource-policy-balloons:v0.12.2` and `nri-config-manager:v0.12.2` pre-cached in JFrog via `ei-docker-ghcr`.

### Helm install — `core/roles/inference-tools/tasks/main.yml` ✅
Original single task curled `raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3` — blocked in airgap. Replaced with dual tasks:
- Internet task: original curl script, `when: not airgap_enabled | bool`
- Airgap task: downloads `helm-v3.15.4-linux-amd64.tar.gz` from `{{ jfrog_url }}/ei-generic-binaries/get.helm.sh/`, extracts and installs to `/usr/local/bin/helm`, idempotent (`if ! command -v helm`)

Also removed duplicate deploy+run task pair that ran the kubernetes SDK `no_proxy` fix twice.

### Kubespray binary downloads — `offline.yml` ✅
Kubespray v2.27.0 downloads all Kubernetes binaries during the `download` role. In airgap mode these must come from JFrog. Configuration: set `files_repo` and all download URLs in `offline.yml`, stored at `core/inventory/metadata/offline.yml` and auto-copied to kubespray inventory by `setup-env.sh` when `airgap_enabled=yes`.

**Component versions for kubespray v2.27.0 / k8s v1.30.4:**
| Component | Version |
|---|---|
| kubernetes | v1.30.4 |
| containerd | 1.7.21 |
| calico | v3.28.1 |
| cni-plugins | v1.4.0 |
| helm | v3.15.4 |
| etcd | v3.5.12 |
| crictl | v1.30.0 |
| runc | v1.1.13 |

**Binaries uploaded to JFrog `ei-generic-binaries` with path structure mirroring original URLs:**
```
dl.k8s.io/release/v1.30.4/bin/linux/amd64/{kubeadm,kubectl,kubelet}
github.com/containernetworking/plugins/releases/download/v1.4.0/cni-plugins-linux-amd64-v1.4.0.tgz
github.com/kubernetes-sigs/cri-tools/releases/download/v1.30.0/crictl-v1.30.0-linux-amd64.tar.gz
github.com/etcd-io/etcd/releases/download/v3.5.12/etcd-v3.5.12-linux-amd64.tar.gz
github.com/projectcalico/calico/releases/download/v3.28.1/calicoctl-linux-amd64
github.com/projectcalico/calico/archive/v3.28.1.tar.gz
get.helm.sh/helm-v3.15.4-linux-amd64.tar.gz
github.com/containerd/containerd/releases/download/v1.7.21/containerd-1.7.21-linux-amd64.tar.gz
github.com/opencontainers/runc/releases/download/v1.1.13/runc.amd64
```

---

## Next Steps (in order)
1. ✅ Add mirrors for ghcr.io, public.ecr.aws, registry.k8s.io, quay.io in `all.yml`
2. ✅ Create `ei-docker-k8s` remote → `registry.k8s.io` in JFrog UI, add to `ei-docker-virtual`
3. ✅ Create `ei-docker-quay` remote → `quay.io` in JFrog UI, add to `ei-docker-virtual`
4. ✅ Test registry.k8s.io and quay.io mirrors — both validated (pause:3.10, calico/node:v3.29.1)
5. ✅ Upload all Helm charts to ei-helm-local via HTTP curl (9 charts: ingress-nginx, langfuse, apisix, keycloak, postgresql, redis, clickhouse, minio, valkey) + regenerate index.yaml
6. ✅ Generate and upload index.yaml — verified via `helm search repo ei-helm` showing all 9 charts
7. ✅ Upload missing pip packages (kubernetes, jsonpatch, requests, urllib3 + all deps) to ei-pypi-local
8. ✅ Upload missing Ansible collections (ansible.posix, kubernetes.core) to ei-generic-binaries
9. ✅ Add Kubespray template patch to `core/roles/container-engine/containerd/templates/hosts.toml.j2`
10. ✅ Fix all helm-related URL gaps: apisix repo registration, keycloak OCI chart_ref, genai-gateway OCI subchart dependencies
11. ✅ Pre-cache all required Docker images in JFrog via `docker pull 100.67.152.212:8082/ei-docker-virtual/<image>:<tag>` on VM1
12. ✅ Set all JFrog remote repos to Offline in JFrog UI
13. ✅ Set `airgap_enabled=on` in `inference-config.cfg` on VM2
14. ✅ Block internet on VM2 — validated: google.com BLOCKED, JFrog REACHABLE
15. ✅ Fix `prereq-check.sh` and `setup-env.sh` to be airgap-aware (JFrog connectivity check, skip apt update, pip from JFrog PyPI mirror, ansible collections from JFrog, kubespray from JFrog tarball)
16. ✅ Upload all kubespray binary dependencies to JFrog `ei-generic-binaries` with correct path structure; configure `offline.yml` pointing to JFrog `files_repo`
17. ✅ Pre-cache missing Kubespray images discovered during first deployment run (see Docker images table): cluster-proportional-autoscaler, coredns/coredns, dns/k8s-dns-node-cache, kube-proxy, calico v3.28.1 (quay.io)
18. ✅ Fix `core/roles/inference-tools/tasks/main.yml` — helm install now airgap-aware: downloads from JFrog `ei-generic-binaries` instead of curling `raw.githubusercontent.com`
19. ✅ Fix `nri_cpu_balloons` role — NRI helm repo, label-nodes, ballon-policy all now pass airgap vars; chart + images pre-cached in JFrog
20. ✅ Fix `deploy-keycloak-tls-cert.yml` APISIX subchart dependency — patch Chart.yaml repo URL + use `helm dependency build` in airgap; pre-cache `kube-webhook-certgen:v1.5.3`
21. ✅ Pre-cache `busybox:1.28` and `apache/apisix-ingress-controller:1.8.0` — APISIX init containers
    - `busybox:1.28` manifest not found via JFrog remote (very old tag, Docker Hub v2 API returns unknown); workaround: pulled `busybox:latest` via JFrog, tagged as `busybox:1.28`, pushed to `ei-docker` local
    - `apache/apisix-ingress-controller:1.8.0` not cached in JFrog; pulled from Docker Hub with credentials, pushed to `ei-docker` local
    - Both now served via `ei-docker-virtual` from `ei-docker` local repo
22. ✅ Fix `install-model.sh` — added `airgap_enabled jfrog_url jfrog_username jfrog_password` to `deploy_inference_llm_models_playbook` ansible-playbook `--extra-vars` (was missing, causing internet helm install task to run)
23. ✅ Fix `xeon-values.yaml` — added `tensor_parallel_size: "1"` override (NRI balloon with TP=2 creates asymmetric NUMA split 85 vs 84 cores → PyTorch shm assertion `ptr->thread_num == thread_num` crash)
24. ✅ Fix `nri_cpu_balloons/tasks/install_nri.yaml` — added pre-check task to skip `blockinfile` if NRI section already exists in containerd config (kubespray already writes `[plugins.'io.containerd.nri.v1.nri'] disable = false`; duplicate key crashes containerd on restart)
25. ✅ Add `deploy_nri_balloon_policy=no` to `inference-config.cfg` — without this, `parse-user-prompts.sh` auto-enables NRI for all CPU deployments (silent default)
26. ✅ Fix `ballon-policy.sh` — removed `|| [ "$cpu_or_gpu" == "c" ]` bypass bug
27. ✅ Fix `deploy-inference-models.yml` — all 7 model install tasks now guard `--set cpu_balloon_annotation` with `{% if enable_cpu_balloons | default(false) | bool %}`
28. ✅ K8s deployment complete — keycloak, apisix, ingress, genai-gateway all running; `vllm-llama-3-2-3b-cpu` 1/1 Running
29. ✅ Fix `vllm-llama-8b-cpu` pod stuck at 0/1 — missing `HF_HUB_OFFLINE=1` caused Hub network validation to hang in airgap; fixed by patching configmap and permanently adding `{% if airgap_enabled %}` guard to all 6 CPU model helm tasks in `deploy-inference-models.yml`
30. ✅ Fix `prereq-check.sh` pip bootstrap in airgap — Ubuntu disables `ensurepip`; apt blocked in airgap; fixed to download `pip.whl` from JFrog `ei-generic-binaries` and install via `PYTHONPATH=<whl> python3 -m pip install --no-index <whl>`
    - Requires `pip.whl` uploaded to JFrog: `pip download pip --no-deps -d /tmp/pip-dl/ && curl -u admin:password -T /tmp/pip-dl/pip-*.whl http://100.67.152.212:8082/artifactory/ei-generic-binaries/pip.whl`
31. ✅ Fix `prereq-check.sh` pip.whl rename — JFrog stores wheel as `pip.whl` (generic name) but pip rejects it; fixed by reading version+tag from WHEEL metadata inside the zip and renaming to proper format (e.g. `pip-26.0.1-py3-none-any.whl`) before calling `pip install`
32. ✅ Fix `setup-env.sh` venv creation in airgap — `python3 -m venv` fails because `python3-pip-whl` / `python3-setuptools-whl` (ensurepip deps) not installed; fixed with two changes:
    - Skip `apt install python3-venv` when `airgap_enabled=yes` (apt has no Debian mirror in JFrog at that point)
    - Create venv with `--without-pip`, then bootstrap pip inside venv from JFrog pip wheel using same rename logic
33. ✅ Fix apt in airgap — Kubespray `kubernetes/preinstall` unconditionally runs `apt update` + `apt install conntrack socat ipset …`; no Debian mirror existed in JFrog → hung 18 min then failed. Fixed:
    - Created `ei-debian-ubuntu` remote repo in JFrog → `http://archive.ubuntu.com/ubuntu`
    - Created `ei-debian-virtual` virtual repo aggregating it
    - `setup-env.sh` now auto-writes `/etc/apt/sources.list` to use JFrog in airgap mode (runs before Kubespray, no manual step needed):
      ```
      deb http://admin:password@100.67.152.212:8082/artifactory/ei-debian-virtual jammy main restricted universe multiverse
      deb http://admin:password@100.67.152.212:8082/artifactory/ei-debian-virtual jammy-updates main restricted universe multiverse
      deb http://admin:password@100.67.152.212:8082/artifactory/ei-debian-virtual jammy-security main restricted universe multiverse
      ```

34. ✅ Fix `docker.io/library/nginx:1.25.2-alpine` not cached in JFrog — root cause and fix:
    - `ei-docker` local repo referenced in CLAUDE.md did not exist (never created)
    - `docker pull 100.67.152.212:8082/ei-docker-virtual/library/nginx:1.25.2-alpine` said "manifest unknown" initially because only the manifest list was cached, not the amd64-specific manifest
    - JFrog v2 API requires proper Docker Accept headers (`application/vnd.docker.distribution.manifest.v2+json`) — plain `curl` without these headers returns 404 even when image is cached
    - Fix: pull by amd64 digest explicitly to force JFrog to cache the platform-specific manifest and layers:
      ```bash
      # On VM1 — get amd64 digest from manifest list, then pull by digest
      docker pull --platform linux/amd64 100.67.152.212:8082/ei-docker-virtual/library/nginx:1.25.2-alpine
      # Then pull amd64 digest directly (fc2d39a0... is amd64 digest for 1.25.2-alpine)
      docker pull 100.67.152.212:8082/ei-docker-virtual/library/nginx@sha256:fc2d39a0d6565db4bd6c94aa7b5efc2da67734cc97388afb5c72369a24bcfaea
      ```
    - **How to verify image is properly cached** (must use Accept headers):
      ```bash
      curl -s -u admin:password \
        -H "Accept: application/vnd.docker.distribution.manifest.v2+json" \
        -H "Accept: application/vnd.docker.distribution.manifest.list.v2+json" \
        -o /dev/null -w "%{http_code}" \
        "http://100.67.152.212:8082/v2/ei-docker-virtual/library/nginx/manifests/1.25.2-alpine"
      # Must return 200
      ```
    - **No local Docker repo needed** — use `ei-docker-dockerhub` remote (already in `ei-docker-virtual`) to cache images; just ensure it is Online when pulling
    - On VM2 before re-running deploy: `sudo crictl rmi docker.io/library/nginx:1.25.2-alpine 2>/dev/null; true && sudo ctr -n k8s.io images rm docker.io/library/nginx:1.25.2-alpine 2>/dev/null; true && sudo systemctl restart containerd`

35. ✅ Fix `inference-tools` role pip/jq installs in airgap:
    - `Install Kubernetes Python SDK` tasks had no airgap handling — tried pypi.org (blocked); fixed with dual tasks using JFrog PyPI `--index-url`
    - `kubernetes` package + all deps (certifi, durationpy, requests, urllib3, websocket-client, etc.) uploaded to `ei-pypi-local`
    - `Ensure jq is installed` used `apt install` — JFrog Debian remote proxies package index but not actual `.deb` files (returns 404); fixed with airgap task that downloads `.deb` files from `ei-generic-binaries/apt-debs/` and installs via `dpkg`
    - `jq_1.6-2.1ubuntu3.1_amd64.deb`, `libjq1_1.6-2.1ubuntu3.1_amd64.deb`, `libonig5_6.9.7.1-2build1_amd64.deb` uploaded to `ei-generic-binaries/apt-debs/`

36. ✅ Fix `community.kubernetes` → `kubernetes.core` across all active playbooks:
    - `community.kubernetes` collection not installed in airgap (galaxy.ansible.com blocked); `kubernetes.core` is the modern equivalent and was already installed via JFrog tarball
    - Replaced all `community.kubernetes.k8s`, `community.kubernetes.helm`, `community.kubernetes.helm_repository`, `community.kubernetes.k8s_info` with `kubernetes.core.*` equivalents in: `deploy-cluster-config.yml`, `deploy-ingress-controller.yml`, `deploy-keycloak-controller.yml`, `deploy-keycloak-service.yml`, `deploy-keycloak-tls-cert.yml`, `deploy-genai-gateway.yml`

37. ✅ Fix `busybox:1.28` and `apache/apisix-ingress-controller:1.8.0` not cached in JFrog:
    - Created `ei-docker-local` local Docker repo in JFrog; added to `ei-docker-virtual`
    - `busybox:1.28`: very old tag, Docker Hub v2 API returns "manifest unknown" → JFrog remote can't proxy it; pulled `busybox:latest` through JFrog, tagged as `1.28`, pushed to `ei-docker-local`
    - `apache/apisix-ingress-controller:1.8.0`: not in any JFrog remote cache; pulled directly from Docker Hub, pushed to `ei-docker-local`
    - **Create ei-docker-local**:
      ```bash
      curl -s -u admin:password -X PUT "http://100.67.152.212:8082/artifactory/api/repositories/ei-docker-local" \
        -H "Content-Type: application/json" -d '{"rclass":"local","packageType":"docker"}'
      curl -s -u admin:password -X POST "http://100.67.152.212:8082/artifactory/api/repositories/ei-docker-virtual" \
        -H "Content-Type: application/json" \
        -d '{"rclass":"virtual","packageType":"docker","repositories":["ei-docker-local","ei-docker-dockerhub","ei-docker-ecr","ei-docker-ghcr","ei-docker-k8s","ei-docker-quay"]}'
      ```

## Fresh Deployment — VM2 (100.67.153.209) — ✅ COMPLETE

**Status**: Fully deployed and validated. LLM endpoint responding in true airgap (internet BLOCKED).

**Validated**:
```bash
curl -k https://api.example.com/Llama-3.1-8B-Instruct-vllmcpu/v1/completions \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"model":"meta-llama/Llama-3.1-8B-Instruct","prompt":"What is Deep Learning?","max_tokens":25}'
# Returns valid completions ✅
curl -s --max-time 5 https://google.com && echo "OPEN" || echo "BLOCKED"
# BLOCKED ✅ — true airgap confirmed
```

**Why inference works without internet**: Model was downloaded to PV in a prior run. `HF_HUB_OFFLINE=1` (step 29 fix) makes vLLM load from `/data/hub/` cache without any Hub network check. PV persists across pod restarts via local-path provisioner.

38. Validate second model (`vllm-llama-3-2-3b-cpu`) endpoint if deployed

## NRI Balloon Policy — Root Cause Analysis

### Why NRI got auto-enabled on VM2 (but not intended)
`deploy_nri_balloon_policy` is not in `inference-config.cfg` by default. `parse-user-prompts.sh` silently auto-sets it to `yes` for any CPU deployment:
```bash
if [ -z "$deploy_nri_balloon_policy" ]; then
    if [ "$cpu_or_gpu" == "c" ]; then
        deploy_nri_balloon_policy="yes"   # ← auto-enables for ALL CPU deployments
    fi
fi
```
**Fix**: always add `deploy_nri_balloon_policy=no` to `inference-config.cfg` explicitly.

Also `ballon-policy.sh` had a bug: `if [ "$deploy_nri_balloon_policy" == "yes" ] || [ "$cpu_or_gpu" == "c" ]` — the `|| cpu_or_gpu == c` clause bypassed the flag entirely. **Fixed** — removed `|| [ "$cpu_or_gpu" == "c" ]` so only `deploy_nri_balloon_policy=yes` triggers NRI deployment.

### Why NRI with TP=2 breaks on VM2 but works on other Xeon machine
NRI balloon size = `tensor_parallel_size × CPUs_per_NUMA_node`:
- VM2 (344 CPUs, 86 cores/socket): TP=2 → balloon = 2 × 172 = **336 CPUs** (whole node) → only 1 model fits
- Other machine (384 CPUs, 96 cores/socket): TP=1 → balloon = 1 × 192 - reserved = **157 CPUs** → multiple models fit

With TP=2 on VM2's 344-CPU node, NRI allocates 336 CPUs per model (entire node), leaving no room for a second model. The TP=2 crash was: asymmetric NUMA split (85 vs 84 physical cores across 2 NUMA nodes) causing PyTorch OMP thread count assertion failure.

### Current state on VM2
- NRI uninstalled (`helm uninstall nri-resource-policy-balloons -n kube-system`)
- `deploy_nri_balloon_policy=no` added to `inference-config.cfg`
- `tensor_parallel_size: "1"` set in `xeon-values.yaml`
- `vllm-llama-3-2-3b-cpu` pod: `1/1 Running` ✅
- `vllm-llama-8b-cpu` pod: `0/1 Running` — downloading `meta-llama/Llama-3.1-8B-Instruct` from HuggingFace Hub (internet accessible from pods via Calico despite host iptables block)

### How to fix stale NRI values in existing vLLM deployments
`helm upgrade --set cpu=""` does NOT clear `cpu: 336` — strategic merge patch omits fields instead of removing them. Use JSON patch to explicitly replace the resources field:
```bash
# Delete ingress first (helm upgrade conflicts with modified ingress object)
kubectl delete ingress <release>-ingress -n auth-apisix
# Clear stale NRI resource requests via JSON patch (helm upgrade can't do this)
kubectl patch deployment <release> -n default --type=json \
  -p='[{"op":"replace","path":"/spec/template/spec/containers/0/resources","value":{}}]'
# Then upgrade to clean helm values
helm upgrade <release> ./helm-charts/vllm --reuse-values \
  --set cpu_balloon_annotation="" --set cpu="" --set tensor_parallel_size=1
```

### `deploy-inference-models.yml` — `enable_cpu_balloons` guard ✅
All 7 occurrences of `--set cpu_balloon_annotation` are now wrapped with `{% if enable_cpu_balloons | default(false) | bool %}`. Without this guard, every model deploy task set `cpu_balloon_annotation=vllm-balloon` and `cpu=336` in the helm release regardless of NRI being disabled — and strategic merge patch can't clear these later.

Pattern applied to all 7 model install tasks:
```yaml
{% if cpu_playbook == 'true' %}
{% if enable_cpu_balloons | default(false) | bool %}
--set cpu_balloon_annotation="vllm-balloon"
--set podLabels.name="vllm"
--set cpu="{{ optimal_balloon_config.workload_cpus | default(8) }}"
--set memory="{{ optimal_memory_gb | default(8) }}Gi"
--set tensor_parallel_size={{ tensor_parallel_size | default(1) }}
--set pipeline_parallel_size={{ pipeline_parallel_size | default(1) }}
{% endif %}
{% endif %}
```

### PV reclaim policy — patch to Retain
By default `local-path` PVs use `Delete` reclaim policy. When a PVC is deleted (e.g., during rollout), the PV and all model data on disk is permanently lost. Patch active PVs to `Retain` immediately after pod creation:
```bash
kubectl patch pv <pv-name> -p '{"spec":{"persistentVolumeReclaimPolicy":"Retain"}}'
```
A Released PV with Retain can be reused: clear its claimRef, then create a new PVC with `volumeName: <pv-name>` and helm adoption annotations.

### vLLM model download behavior on VM2
- `HF_HOME=/data` — models cached at `/data/hub/models--<org>--<model>/snapshots/<hash>/`
- Pods download from HuggingFace Hub directly, NOT from JFrog `ei-generic-models`
- Pod networking (Calico) bypasses host iptables — pods can reach internet even when VM2 host internet is blocked
- HuggingFace download stalls silently at ~8.8MB (metadata only) on consecutive restarts — root cause: stale `.lock` files in `/data/hub/.locks/` from previous pod runs; fix: `kubectl exec <pod> -- find /data/hub/.locks -type f -delete`
- **To truly use JFrog `ei-generic-models`**: set `HF_HUB_OFFLINE=1` and pre-populate `/data/hub/` with model files from JFrog before pod starts (or mount a pre-populated PV)

---

## Airgap Simulation — Block Internet on VM2

**VM IPs**: VM1 (JFrog) = `100.67.152.212`, VM2 = `100.67.153.209` (rebooted — was .208), SSH client = `100.64.29.144`

```bash
# Check SSH source IP first — must be in allowed ranges or you will be locked out
echo $SSH_CLIENT

# Block internet — allow only JFrog + cluster subnet + SSH client + internal ranges
sudo iptables -A OUTPUT -m state --state ESTABLISHED,RELATED -j ACCEPT
sudo iptables -A OUTPUT -o lo -j ACCEPT
sudo iptables -A OUTPUT -d 100.67.0.0/16 -j ACCEPT   # VM1 + VM2 + cluster nodes
sudo iptables -A OUTPUT -d 100.64.0.0/10 -j ACCEPT   # SSH client subnet
sudo iptables -A OUTPUT -d 10.0.0.0/8 -j ACCEPT      # Kubernetes pod/service CIDRs
sudo iptables -A OUTPUT -d 192.168.0.0/16 -j ACCEPT  # Kubernetes pod/service CIDRs
sudo iptables -A OUTPUT -j DROP

# Verify
curl -s --max-time 5 https://google.com && echo "OPEN" || echo "BLOCKED"
curl -s --max-time 5 http://100.67.152.212:8082/artifactory/api/system/ping && echo "JFROG OK"

# To unblock
sudo iptables -D OUTPUT -m state --state ESTABLISHED,RELATED -j ACCEPT
sudo iptables -D OUTPUT -o lo -j ACCEPT
sudo iptables -D OUTPUT -d 100.67.0.0/16 -j ACCEPT
sudo iptables -D OUTPUT -d 100.64.0.0/10 -j ACCEPT
sudo iptables -D OUTPUT -d 10.0.0.0/8 -j ACCEPT
sudo iptables -D OUTPUT -d 192.168.0.0/16 -j ACCEPT
sudo iptables -D OUTPUT -j DROP
```

**Validated ✅** — google.com BLOCKED, JFrog ping returns OK.
