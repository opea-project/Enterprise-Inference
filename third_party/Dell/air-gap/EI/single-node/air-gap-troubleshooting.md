# Airgapped Deployment - Troubleshooting Guide

This document covers common failures encountered during airgapped deployment of Enterprise Inference, their root causes, and fixes. Issues are grouped by the stage at which they occur.

---

## 1. Pre-flight / Prerequisites Stage

### pip install fails - ensurepip not available

**Symptom**: `python3 -m venv` fails or pip is not found after venv creation.

**Root cause**: Ubuntu disables `ensurepip` by default. `python3-pip` cannot be installed via apt in airgap before the Debian mirror is configured.

**Fix**: Upload `pip.whl` to JFrog and bootstrap pip from it:
```bash
# On VM1 - download and upload pip wheel
pip download pip --no-deps -d /tmp/pip-dl/
curl -u admin:password -T /tmp/pip-dl/pip-*.whl \
  "http://100.67.152.212:8082/artifactory/ei-generic-binaries/pip.whl"
```
The deployment script (`setup-env.sh`) handles the rest automatically - it downloads the wheel, reads the version from its WHEEL metadata, renames it to the proper format (e.g. `pip-26.0.1-py3-none-any.whl`), and installs it.

---

### pip install fails - package not found in JFrog PyPI

**Symptom**: `pip install` fails with `404 Not Found` or `No matching distribution found` even though the package appears in the JFrog simple index.

**Root cause**: JFrog's PyPI simple index lists the package name but the `.whl` file was never uploaded - only the index entry exists.

**Fix**: Upload the missing wheel file physically to `ei-pypi-local`:
```bash
pip download <package>==<version> --no-deps -d /tmp/wheels/
curl -u admin:password -T /tmp/wheels/<package>.whl \
  "http://100.67.152.212:8082/artifactory/ei-pypi-local/<package>.whl"
```

---

### Ansible collection install fails - galaxy.ansible.com unreachable

**Symptom**: `ansible-galaxy collection install` hangs or fails with a connection error.

**Root cause**: `galaxy.ansible.com` is not reachable in airgap. Collections must come from JFrog.

**Fix**: Upload collection tarballs to `ei-generic-binaries/ansible-collections/` with the `-latest` suffix. `setup-env.sh` downloads them automatically:
```bash
ansible-galaxy collection download kubernetes.core:6.3.0 -p /tmp/
curl -u admin:password -T /tmp/kubernetes-core-6.3.0.tar.gz \
  "http://100.67.152.212:8082/artifactory/ei-generic-binaries/ansible-collections/kubernetes-core-latest.tar.gz"
```

> **Warning**: Files must use the `-latest` suffix (e.g. `kubernetes-core-latest.tar.gz`). Versioned filenames (e.g. `kubernetes-core-6.3.0.tar.gz`) are silently skipped by `setup-env.sh`.

---

### `community.kubernetes` module not found

**Symptom**: Playbook fails with:
```
couldn't resolve module/action 'community.kubernetes.k8s'
```

**Root cause**: `community.kubernetes` is deprecated and not installed in airgap. The modern equivalent is `kubernetes.core`, which is installed via JFrog tarball.

**Fix**: All EI playbooks have been migrated to `kubernetes.core.*`. If you see this error in a custom playbook, replace all occurrences:
```bash
sed -i 's/community\.kubernetes\./kubernetes.core./g' <playbook>.yml
```

---

### apt-get update fails or hangs in airgap

**Symptom**: `apt-get update` hangs for 10-18 minutes then fails with connection timeout.

**Root cause**: No Debian mirror is configured in JFrog, or `/etc/apt/sources.list` still points to `archive.ubuntu.com`.

**Fix**: `setup-env.sh` automatically rewrites `/etc/apt/sources.list` to point to JFrog when `airgap_enabled=yes`. If running manually:
```bash
sudo tee /etc/apt/sources.list > /dev/null << EOF
deb [trusted=yes] http://admin:password@100.67.152.212:8082/artifactory/ei-debian-virtual jammy main restricted universe multiverse
deb [trusted=yes] http://admin:password@100.67.152.212:8082/artifactory/ei-debian-virtual jammy-updates main restricted universe multiverse
deb [trusted=yes] http://admin:password@100.67.152.212:8082/artifactory/ei-debian-virtual jammy-security main restricted universe multiverse
EOF
sudo apt-get update
```

---

### apt-get install returns 404 for .deb files

**Symptom**: `apt-get install jq` (or any package) fails with `404 Not Found` even after `apt-get update` succeeds.

**Root cause**: JFrog's Debian remote correctly proxies the package index (`Packages.gz`, `Release`) but returns 404 for actual `.deb` pool file downloads. This is a JFrog Debian remote limitation.

**Fix**: Upload the required `.deb` files directly to `ei-generic-binaries/apt-debs/` and install via `dpkg`. The `inference-tools` role handles `jq` automatically in airgap mode. For other packages:
```bash
# On VM1 - download debs
apt-get download <package>
# Upload to JFrog
curl -u admin:password -T <package>.deb \
  "http://100.67.152.212:8082/artifactory/ei-generic-binaries/apt-debs/<package>.deb"

# On VM2 - install
curl -sfL -u admin:password \
  -o /tmp/<package>.deb \
  "http://100.67.152.212:8082/artifactory/ei-generic-binaries/apt-debs/<package>.deb"
sudo dpkg -i /tmp/<package>.deb
```

---

### Kubespray clone fails - github.com unreachable

**Symptom**: `git clone https://github.com/kubernetes-sigs/kubespray.git` fails.

**Root cause**: GitHub is not reachable in airgap.

**Fix**: Upload a kubespray tarball to JFrog before deploying. `setup-env.sh` downloads it automatically when `airgap_enabled=yes`:
```bash
# On VM1
git clone https://github.com/kubernetes-sigs/kubespray.git
cd kubespray && git checkout v2.27.0 && cd ..
tar -czf kubespray.tar.gz kubespray/
curl -u admin:password -T kubespray.tar.gz \
  "http://100.67.152.212:8082/artifactory/ei-generic-binaries/kubespray.tar.gz"
```

---

### Windows CRLF line endings break bash scripts

**Symptom**: Scripts fail with errors like `function not found` or `bad interpreter: No such file or directory` when copied from a Windows machine.

**Root cause**: Windows adds `\r` (carriage return) to line endings. Bash interprets function names as `functionname\r` which does not match the call site.

**Fix**: After copying files to VM2, strip CRLF:
```bash
find ~/Enterprise-Inference -name "*.sh" -o -name "*.yml" -o -name "*.yaml" -o -name "*.cfg" | \
  xargs sed -i 's/\r//'
```

---

## 2. Kubespray / Kubernetes Bootstrap Stage

### Binary download fails - 404 from JFrog

**Symptom**: Kubespray `download` role fails with:
```
trying next host - response was http.StatusNotFound" host="100.67.152.212:8082"
```

**Root cause**: Kubespray constructs binary download URLs from component versions. The binary was not uploaded to JFrog with the matching path structure.

**Fix**: Upload the missing binary to JFrog preserving the exact URL path. Check which binary failed and upload it:
```bash
# Example: missing kubelet
curl -LO https://dl.k8s.io/release/v1.30.4/bin/linux/amd64/kubelet
curl -u admin:password -T kubelet \
  "http://100.67.152.212:8082/artifactory/ei-generic-binaries/dl.k8s.io/release/v1.30.4/bin/linux/amd64/kubelet"
```
See `core/inventory/metadata/offline.yml` for the full list of expected paths.

---

### containerd mirror not working - image pulls go to internet

**Symptom**: Images are pulled from the original registry instead of JFrog. Confirmed by: `sudo journalctl -u containerd | grep "bytes read=0"`.

**Root cause**: `hosts.toml` is misconfigured. Common mistakes:

1. Mirror host URL missing `/v2/` prefix
2. `skip_verify` field present (even `skip_verify: false` breaks HTTP mirrors)
3. Mirror not listed under the correct registry

**Fix**: Verify `hosts.toml` for each registry:
```bash
cat /etc/containerd/certs.d/docker.io/hosts.toml
```
Expected format (no `skip_verify` field at all):
```toml
server = "https://docker.io"
[host."http://100.67.152.212:8082/v2/ei-docker-virtual"]
  capabilities = ["pull", "resolve"]
  override_path = true
```

Apply for all registries:
```bash
for reg in docker.io ghcr.io registry.k8s.io quay.io public.ecr.aws; do
  sudo mkdir -p /etc/containerd/certs.d/$reg
  sudo tee /etc/containerd/certs.d/$reg/hosts.toml <<EOF
server = "https://$reg"
[host."http://100.67.152.212:8082/v2/ei-docker-virtual"]
  capabilities = ["pull","resolve"]
  override_path = true
EOF
done
sudo systemctl restart containerd
```

---

### Image pull fails with `manifest unknown` despite image being in JFrog

**Symptom**: containerd fails to pull an image with `manifest unknown` even though the image appears in the JFrog catalog.

**Root cause**: JFrog cached only the multi-arch manifest list, not the amd64-specific manifest. containerd requests the platform manifest and gets 404.

**Fix**: On VM1, pull by amd64 platform digest to force JFrog to cache the platform-specific manifest:
```bash
docker pull --platform linux/amd64 100.67.152.212:8082/ei-docker-virtual/library/nginx:1.25.2-alpine
# Then pull by digest
docker pull 100.67.152.212:8082/ei-docker-virtual/library/nginx@sha256:fc2d39a0...
```

Verify image is properly cached (must use Docker Accept headers):
```bash
curl -s -u admin:password \
  -H "Accept: application/vnd.docker.distribution.manifest.v2+json" \
  -H "Accept: application/vnd.docker.distribution.manifest.list.v2+json" \
  -o /dev/null -w "%{http_code}" \
  "http://100.67.152.212:8082/v2/ei-docker-virtual/library/nginx/manifests/1.25.2-alpine"
# Must return 200 (plain curl without Accept headers returns 404 even when cached)
```

---

### Image pull fails for very old tags (e.g. `busybox:1.28`)

**Symptom**: JFrog remote returns `manifest unknown` for old tags. Docker Hub v2 API no longer serves manifests for these tags.

**Fix**: Pull a working equivalent tag, retag, and push to `ei-docker-local`:
```bash
JFROG=100.67.152.212:8082
docker pull $JFROG/ei-docker-virtual/library/busybox:latest
docker tag $JFROG/ei-docker-virtual/library/busybox:latest $JFROG/ei-docker-local/library/busybox:1.28
docker push $JFROG/ei-docker-local/library/busybox:1.28
```
`ei-docker-local` is a local Docker repo in JFrog. Ensure it is a member of `ei-docker-virtual`.

---

### containerd HTML blob corruption loop

**Symptom**: Pod stays in `ImagePullBackOff`. containerd logs show repeated pull attempts for the same image. The cached blob is actually an HTML 404 error page.

**Root cause**: containerd pulled an HTML error page from JFrog (before the mirror was correctly configured) and cached it as a manifest blob. The CRI backoff loop re-caches it on every retry.

**Fix**: Remove the corrupted image from all containerd layers:
```bash
IMAGE="docker.io/library/nginx:1.25.2-alpine"
sudo crictl rmi $IMAGE 2>/dev/null; true
sudo ctr -n k8s.io images rm $IMAGE 2>/dev/null; true
# Delete the bad blob file directly (find the sha256 from the error log)
sudo rm -f /var/lib/containerd/io.containerd.content.v1.content/blobs/sha256/<bad-sha256>
sudo systemctl restart containerd
```

---

### Docker Hub rate limit hit when pre-caching images on VM1

**Symptom**: `docker pull` returns `toomanyrequests: You have reached your pull rate limit`.

**Fix**: Authenticate with Docker Hub before pulling:
```bash
docker login -u <dockerhub-user> -p <personal-access-token>
```
Rotate the PAT after use. Docker Hub free accounts allow 100 pulls/6h unauthenticated, 200/6h authenticated.

---

## 3. Helm / Application Deployment Stage

### helm repo add fails - upstream URL unreachable

**Symptom**: `helm repo add https://kubernetes.github.io/ingress-nginx` fails with connection error.

**Root cause**: Upstream Helm repo URLs are blocked in airgap.

**Fix**: Use the JFrog virtual Helm repo instead. All EI playbooks handle this automatically when `airgap_enabled=yes`. If running helm manually:
```bash
helm repo add ingress-nginx http://100.67.152.212:8082/artifactory/ei-helm-virtual \
  --username admin --password password --force-update
helm repo update
```

---

### `helm dependency update` contacts internet in airgap

**Symptom**: `helm dependency update` fails or hangs trying to contact `charts.apiseven.com`, `registry-1.docker.io`, or other upstream URLs.

**Root cause**: `Chart.yaml` dependency entries contain hardcoded upstream `repository` URLs. Helm resolves these directly, bypassing registered repos and containerd mirrors.

**Fix**: Use airgap-specific dependency resolution:
1. Pre-pull subchart tarballs from JFrog registered repo
2. Place them in `charts/` directory
3. Patch `Chart.yaml` to replace upstream URLs with JFrog URL
4. Run `helm dependency build` instead of `helm dependency update`

This is handled automatically by EI playbooks (`deploy-keycloak-tls-cert.yml`, `deploy-genai-gateway.yml`) when `airgap_enabled=yes`.

---

### Keycloak chart install fails - OCI pull contacts docker.io

**Symptom**: `helm install` with `chart_ref: oci://registry-1.docker.io/bitnamicharts/keycloak` fails in airgap.

**Root cause**: Helm uses its own HTTP client for OCI pulls, bypassing containerd mirrors entirely.

**Fix**: Use the JFrog Helm repo instead of OCI:
```bash
helm repo add ei-helm http://100.67.152.212:8082/artifactory/ei-helm-virtual \
  --username admin --password password --force-update
helm install keycloak ei-helm/keycloak --version 22.1.0
```
EI playbooks do this automatically when `airgap_enabled=yes`.

---

### Helm install fails - chart not found in index

**Symptom**: `helm search repo ei-helm` returns no results or does not show expected charts.

**Root cause**: `index.yaml` was not uploaded or is outdated after adding new charts.

**Fix**: Regenerate and re-upload `index.yaml`:
```bash
cd /tmp/helm-charts-dir
helm repo index . --url http://100.67.152.212:8082/artifactory/ei-helm-local
curl -u admin:password -T index.yaml \
  "http://100.67.152.212:8082/artifactory/ei-helm-local/index.yaml"
helm repo update
helm search repo ei-helm
```

---

## 4. vLLM / Model Deployment Stage

### vLLM pod stuck at 0/1 - HuggingFace network timeout

**Symptom**: Pod shows `0/1 Running`. Logs stop after OMP thread binding with no model file activity. No crash, just silence.

**Root cause**: `HF_HUB_OFFLINE` is not set. The HuggingFace Hub library makes network calls to `huggingface.co` to validate cached model metadata. These calls hang silently in airgap.

**Fix**: Patch the pod's ConfigMap to set offline mode:
```bash
kubectl patch configmap <model>-config --type=merge \
  -p '{"data":{"HF_HUB_OFFLINE":"1","TRANSFORMERS_OFFLINE":"1"}}'
kubectl rollout restart deployment <model>
```

Permanent fix: add to `core/helm-charts/vllm/xeon-values.yaml`:
```yaml
defaultModelConfigs:
  configMapValues:
    HF_HUB_OFFLINE: "1"
    TRANSFORMERS_OFFLINE: "1"
```

---

### Model download stalls at ~8.8MB on pod restart

**Symptom**: vLLM pod restarts and the model download appears to start but stops at 8.8MB (metadata only). No further progress.

**Root cause**: Stale `.lock` files in `/data/hub/.locks/` from a previous pod run prevent the download from resuming.

**Fix**:
```bash
kubectl exec <pod> -- find /data/hub/.locks -type f -delete
kubectl rollout restart deployment <model>
```

---

### Model files not found with `HF_HUB_OFFLINE=1`

**Symptom**: vLLM crashes with `OSError: We have no connection to the internet and we cannot find the cached files`.

**Root cause**: Model files were manually copied to the PV but not in the HuggingFace Hub cache directory format (`/data/hub/models--<org>--<model>/snapshots/<hash>/`). The Hub library cannot locate them.

**Fix**: Pre-populate the PV using `huggingface_hub.snapshot_download()` which creates the correct directory structure:
```python
from huggingface_hub import snapshot_download
snapshot_download(
  'meta-llama/Llama-3.1-8B-Instruct',
  local_dir='/data/hub/models--meta-llama--Llama-3.1-8B-Instruct/snapshots/<hash>/',
  local_files_only=False  # set True if files already present
)
```

---

### PV deleted and model data lost after pod restart

**Symptom**: After a pod is deleted and recreated, the model starts downloading from scratch.

**Root cause**: `local-path` PVs use `Delete` reclaim policy by default. When the PVC is deleted, the PV and all data on disk is permanently removed.

**Fix**: Patch active PVs to `Retain` immediately after pod creation:
```bash
kubectl patch pv <pv-name> -p '{"spec":{"persistentVolumeReclaimPolicy":"Retain"}}'
```
To reuse a Released PV after PVC deletion:
```bash
# Clear the claimRef so PV becomes Available
kubectl patch pv <pv-name> --type=json \
  -p='[{"op":"remove","path":"/spec/claimRef"}]'
# Create new PVC referencing the PV by name
```

---

## 5. NRI Balloon Policy Issues

### NRI auto-enabled despite `deploy_nri_balloon_policy=no`

**Symptom**: NRI balloon policy deploys on all CPU deployments regardless of config setting.

**Root cause**: Three compounding bugs:
1. `parse-user-prompts.sh` silently auto-sets `deploy_nri_balloon_policy=yes` for any CPU deployment when the variable is unset
2. `ballon-policy.sh` had `|| [ "$cpu_or_gpu" == "c" ]` bypass that triggered NRI for all CPU deployments regardless of the flag
3. `deploy-inference-models.yml` unconditionally passed `--set cpu_balloon_annotation` to all 7 model tasks

**Fix**: Both code bugs have been fixed. Always set `deploy_nri_balloon_policy=no` explicitly in `inference-config.cfg` to suppress NRI.

---

### vLLM pods have stale NRI resource requests after NRI uninstall

**Symptom**: vLLM pods show `cpu: 336` resource requests even after NRI is uninstalled. `helm upgrade --set cpu=""` does not clear them.

**Root cause**: `helm upgrade` uses strategic merge patch which omits fields rather than removing them. Existing `cpu: 336` value is not cleared.

**Fix**: Use JSON patch to explicitly replace the resources field:
```bash
# Delete ingress first (helm upgrade conflicts with modified ingress)
kubectl delete ingress <release>-ingress -n auth-apisix

# Clear stale NRI resource requests
kubectl patch deployment <release> -n default --type=json \
  -p='[{"op":"replace","path":"/spec/template/spec/containers/0/resources","value":{}}]'

# Upgrade with clean values
helm upgrade <release> ./helm-charts/vllm --reuse-values \
  --set cpu_balloon_annotation="" --set cpu="" --set tensor_parallel_size=1
```

---

### NRI with TP=2 crashes with PyTorch assertion error

**Symptom**: vLLM pod crashes with `ptr->thread_num == thread_num` assertion in PyTorch OMP layer.

**Root cause**: On asymmetric NUMA nodes (e.g. 85 vs 84 cores), NRI with `tensor_parallel_size=2` splits the balloon unevenly across NUMA nodes. PyTorch asserts that OMP thread counts are symmetric.

**Fix**: Set `tensor_parallel_size: "1"` in `core/helm-charts/vllm/xeon-values.yaml`.

---

## 6. JFrog Configuration Issues

### JFrog returns 404 to curl but image is shown as cached in UI

**Symptom**: `curl http://100.67.152.212:8082/v2/ei-docker-virtual/library/nginx/manifests/1.25.2-alpine` returns 404 but the image appears in JFrog storage.

**Root cause**: The JFrog v2 Docker API requires specific `Accept` headers to serve manifests. Plain curl without headers returns 404.

**Fix**: Always use Docker Accept headers when verifying image cache:
```bash
curl -s -u admin:password \
  -H "Accept: application/vnd.docker.distribution.manifest.v2+json" \
  -H "Accept: application/vnd.docker.distribution.manifest.list.v2+json" \
  -o /dev/null -w "%{http_code}" \
  "http://100.67.152.212:8082/v2/ei-docker-virtual/library/nginx/manifests/1.25.2-alpine"
```

---

### JFrog remote repo fetches from internet despite being set to Offline

**Symptom**: JFrog still serves new images/packages not previously cached after being set to Offline.

**Root cause**: The repo was not actually saved as Offline, or the virtual repo routing picks up a different remote that is still Online.

**Fix**: In JFrog UI, verify each remote repo is set to Offline:
- Admin → Repositories → Edit each remote → Advanced → Online/Offline → set to Offline
- Check all remotes: `ei-docker-dockerhub`, `ei-docker-ecr`, `ei-docker-ghcr`, `ei-docker-k8s`, `ei-docker-quay`

---

### How to find which image caused a 404 during deployment

The image name comes from Kubespray's defaults. Look for this pattern in the deployment log:
```
trying next host - response was http.StatusNotFound" host="100.67.152.212:8082"
trying next host" error="...dial tcp...: i/o timeout" host=<registry>
```

Check `core/kubespray/roles/kubespray-defaults/defaults/main/download.yml` for the image name and tag. Pre-cache on VM1:
```bash
# Set the relevant remote to Online in JFrog UI first
docker pull 100.67.152.212:8082/ei-docker-virtual/<image>:<tag>
# Then set back to Offline
```

---

## 7. Verification Commands

### Check JFrog is reachable from VM2
```bash
curl -s --max-time 5 http://100.67.152.212:8082/artifactory/api/system/ping && echo "JFrog OK" || echo "JFrog unreachable"
```

### Confirm internet is blocked on VM2
```bash
curl -s --max-time 5 https://google.com && echo "FAIL - internet open" || echo "OK - internet blocked"
```

### Confirm image pulled from JFrog (not internet)
```bash
# bytes > 0 means JFrog mirror was used
sudo journalctl -u containerd --no-pager | grep "stop pulling image" | grep -v "bytes read=0"

# Or watch JFrog request log on VM1 for VM2's IP
tail -f /var/opt/jfrog/artifactory/log/request.log | grep 100.67.153.209
```

### List all images cached in JFrog
```bash
curl -s -u admin:password \
  http://100.67.152.212:8082/artifactory/api/docker/ei-docker-virtual/v2/_catalog | jq .repositories[]
```

### Check tags for a specific image
```bash
curl -s -u admin:password \
  "http://100.67.152.212:8082/artifactory/api/docker/ei-docker-virtual/v2/library/nginx/tags/list" | jq .
```

### List all files in a generic repo path
```bash
curl -s -u admin:password \
  "http://100.67.152.212:8082/artifactory/api/storage/ei-generic-binaries/ansible-collections" | jq '.children[].uri'
```

### List all PyPI packages in JFrog
```bash
curl -s -u admin:password \
  "http://100.67.152.212:8082/artifactory/api/storage/ei-pypi-local" | jq '.children[].uri'
```
