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

**Docker images** (cached in JFrog remote repos via `ei-docker-virtual`):
| Image | Tag | Registry |
|---|---|---|
| vllm-cpu-release-repo | v0.10.2 | public.ecr.aws |
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
| ingress-nginx/kube-webhook-certgen | v1.5.1 | registry.k8s.io |
| ubuntu | 22.04 | docker.io |
| All Kubernetes components | v1.31.4 | registry.k8s.io |
| calico (cni, node, kube-controllers) | v3.29.1 | docker.io |
| coredns | v1.11.3 | registry.k8s.io |
| pause | 3.10 | registry.k8s.io |
| local-path-provisioner | v0.0.24 | docker.io |

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
- pip installs: when `airgap_enabled=yes`, uses `--index-url http://${jfrog_username}:${jfrog_password}@${jfrog_host}/artifactory/api/pypi/ei-pypi-virtual/simple --trusted-host ${jfrog_host}`
- kubespray clone: when `airgap_enabled=yes` and `$KUBESPRAYDIR` doesn't exist, downloads `kubespray.tar.gz` from `${jfrog_url}/ei-generic-binaries/kubespray.tar.gz` and extracts to `$(dirname $KUBESPRAYDIR)` instead of git cloning
- Ansible collections: when `airgap_enabled=yes`, downloads each collection tarball from `${jfrog_url}/ei-generic-binaries/ansible-collections/${coll_file}-latest.tar.gz` and installs via `ansible-galaxy collection install <tarball>`; collections attempted: `kubernetes-core`, `ansible-posix`, `community-kubernetes`, `community-general`

**Important**: When copying these files from Windows to Linux via SCP, always run `sed -i 's/\r//' <file>` on VM2 to strip Windows CRLF line endings, otherwise bash function names get `\r` appended and are not found.

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
16. Run full deployment on VM2: `cd ~/Enterprise-Inference/core && ./inference-stack-deploy.sh`
17. Validate all pods reach Running state and LLM endpoint responds

## Airgap Simulation — Block Internet on VM2

**VM IPs**: VM1 (JFrog) = `100.67.152.212`, VM2 = `100.67.153.208`, SSH client = `100.64.29.144`

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
