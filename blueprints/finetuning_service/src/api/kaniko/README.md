# Kaniko Build System

Enterprise-grade Docker image building using Kaniko in Kubernetes, without requiring Docker daemon.

## 📋 Overview

This directory contains Kaniko-based build configuration for building Docker images directly in Kubernetes. Kaniko builds container images from a Dockerfile inside a Kubernetes cluster without privileged access or Docker daemon.

### Why Kaniko?

- ✅ **No Docker Daemon Required**: Builds in standard Kubernetes pods
- ✅ **Secure**: No privileged containers needed
- ✅ **Layer Caching**: Fast incremental builds (~30s for code changes)
- ✅ **Kubernetes Native**: Runs as standard Job
- ✅ **Reproducible**: Consistent builds across environments

---

## 📁 Files

```
kaniko/
├── kaniko-job.yaml          # Kubernetes Job definition
├── deploy-finetuning.sh     # Build orchestration script
└── README.md                # This file
```

---

## 🚀 Quick Start

### Basic Usage

```bash
# Build with defaults
./kaniko/deploy-finetuning.sh

# Build with custom tag
export IMAGE_TAG=v1.2.3
./kaniko/deploy-finetuning.sh

# Build with custom registry
export REGISTRY_URL=my-registry.example.com:5000
export IMAGE_TAG=latest
./kaniko/deploy-finetuning.sh

# Debug mode
DEBUG=1 ./kaniko/deploy-finetuning.sh
```

---

## 📖 Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `REGISTRY_URL` | `registry.kube-system.svc.cluster.local:5000` | Docker registry URL |
| `IMAGE_TAG` | `latest` | Image tag to build |
| `NAMESPACE` | `finetuning` | Kubernetes namespace |
| `BUILD_TIMEOUT` | `600` | Build timeout in seconds (10 min) |
| `BUILD_CONTEXT` | Auto-detected | Path to build context |
| `DEBUG` | `0` | Enable debug output (set to `1`) |

### Example Configurations

#### Development Build
```bash
export NAMESPACE=finetuning-dev
export IMAGE_TAG=dev-$(git rev-parse --short HEAD)
export BUILD_TIMEOUT=300
./kaniko/deploy-finetuning.sh
```

#### Production Build
```bash
export NAMESPACE=finetuning-prod
export IMAGE_TAG=v$(cat VERSION)
export BUILD_TIMEOUT=900
./kaniko/deploy-finetuning.sh
```

#### Custom Registry
```bash
export REGISTRY_URL=registry.mydomain.com:5000
export IMAGE_TAG=stable
./kaniko/deploy-finetuning.sh
```

---

## 🏗️ How It Works

### Build Process Flow

```
┌─────────────────────────────────────────┐
│ 1. Validate Environment                 │
│    ✓ Check kubectl connectivity         │
│    ✓ Verify Dockerfile exists           │
│    ✓ Check build context path           │
└─────────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────────┐
│ 2. Setup Namespace & Secrets            │
│    ✓ Create namespace if needed         │
│    ✓ Copy registry-secret                │
└─────────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────────┐
│ 3. Clean Up Old Jobs                    │
│    ✓ Delete previous build jobs         │
│    ✓ Wait for deletion                  │
└─────────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────────┐
│ 4. Create Kaniko Build Job              │
│    ✓ Apply kaniko-job.yaml              │
│    ✓ Mount build context                │
└─────────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────────┐
│ 5. Stream Build Logs                    │
│    ✓ Wait for pod to start              │
│    ✓ Follow build logs in real-time     │
└─────────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────────┐
│ 6. Verify Build Status                  │
│    ✓ Wait for job completion            │
│    ✓ Check success/failure               │
│    ✓ Show build time and image info     │
└─────────────────────────────────────────┘
```

### Kaniko Job Configuration

The `kaniko-job.yaml` defines a Kubernetes Job with:

- **Pinned Version**: `v1.23.2` for reproducibility
- **Resource Limits**:
  - Requests: 512Mi RAM, 500m CPU
  - Limits: 2Gi RAM, 2000m CPU
- **Security Context**:
  - Runs as non-root user (UID 1000)
  - Drops ALL capabilities
  - No privilege escalation
- **Build Features**:
  - Layer caching enabled
  - Compressed caching disabled (faster in-cluster)
  - Snapshot mode: redo
  - New run implementation
- **Auto-Cleanup**: Jobs auto-delete after 1 hour (3600s)

---

## 📊 Build Performance

### Expected Build Times

| Scenario | First Build | Cached Build |
|----------|-------------|--------------|
| Full rebuild | 3-5 minutes | N/A |
| Code changes only | 2-3 minutes | ~30 seconds |
| Dependency changes | 3-4 minutes | 1-2 minutes |
| No changes | 2 minutes | ~20 seconds |

### Cache Optimization

Kaniko uses layer caching stored in the registry:

```yaml
Cache Location: ${REGISTRY_URL}/finetuning-service-cache
Cache Strategy: Layer-based
Cache Invalidation: Automatic when Dockerfile changes
```

**Tips for faster builds:**
- Order Dockerfile from least to most frequently changing
- Group related RUN commands
- Use multi-stage builds
- Minimize layers

---

## 🔧 Troubleshooting

### Common Issues

#### 1. Build Fails with "Cannot connect to registry"

**Cause:** Registry not accessible or credentials missing

**Solution:**
```bash
# Check registry connectivity
kubectl run test-registry --rm -i --tty --image=curlimages/curl --restart=Never -- \
  curl -v http://registry.kube-system.svc.cluster.local:5000/v2/

# Verify registry-secret exists
kubectl get secret registry-secret -n kube-system

# Check Kaniko pod logs
kubectl logs -n finetuning -l job-name=kaniko-finetuning-service
```

#### 2. "Dockerfile not found"

**Cause:** Build context path incorrect

**Solution:**
```bash
# Verify Dockerfile location
ls -la $BUILD_CONTEXT/Dockerfile

# Manual override
export BUILD_CONTEXT=/path/to/project
./kaniko/deploy-finetuning.sh
```

#### 3. Build Timeout

**Cause:** Build taking longer than BUILD_TIMEOUT

**Solution:**
```bash
# Increase timeout (in seconds)
export BUILD_TIMEOUT=1200  # 20 minutes
./kaniko/deploy-finetuning.sh
```

#### 4. "Pod not starting"

**Cause:** Resource constraints or node issues

**Solution:**
```bash
# Check pod status
kubectl describe pod -n finetuning -l job-name=kaniko-finetuning-service

# Check events
kubectl get events -n finetuning --sort-by='.lastTimestamp'

# Reduce resource requests in kaniko-job.yaml if needed
```

#### 5. Cache Issues

**Cause:** Corrupted cache or registry issues

**Solution:**
```bash
# Disable cache temporarily
# Edit kaniko-job.yaml: Change --cache=true to --cache=false

# Or clear cache
kubectl delete pvc -n kube-system -l app=docker-registry
```

### Debug Mode

Enable detailed debugging:

```bash
DEBUG=1 ./kaniko/deploy-finetuning.sh
```

This shows:
- All variable values
- Exact commands executed
- Detailed error traces

### Manual Build

If automated script fails, run manually:

```bash
# 1. Export variables
export REGISTRY_URL=registry.kube-system.svc.cluster.local:5000
export IMAGE_TAG=latest
export NAMESPACE=finetuning
export BUILD_CONTEXT=/home/ubuntu/api-finetune-04022026

# 2. Apply job
envsubst < kaniko/kaniko-job.yaml | kubectl apply -f -

# 3. Watch logs
kubectl logs -f -n finetuning -l job-name=kaniko-finetuning-service
```

---

## 🎯 Best Practices

### Security

1. **Always use pinned Kaniko version** (already configured)
2. **Run as non-root** (already configured)
3. **Use minimal base images** in Dockerfile
4. **Scan images** after build:
   ```bash
   trivy image ${REGISTRY_URL}/finetuning-service:${IMAGE_TAG}
   ```

### Performance

1. **Optimize Dockerfile**:
   ```dockerfile
   # Good: Dependencies first (cached)
   COPY requirements.txt .
   RUN pip install -r requirements.txt

   # Then code (changes frequently)
   COPY app/ ./app/
   ```

2. **Use build args** for dynamic values
3. **Minimize layers**: Combine RUN commands
4. **Use .dockerignore**: Exclude unnecessary files

### CI/CD Integration

#### GitLab CI
```yaml
build:
  stage: build
  script:
    - export IMAGE_TAG=$CI_COMMIT_SHORT_SHA
    - ./kaniko/deploy-finetuning.sh
  only:
    - main
```

#### GitHub Actions
```yaml
- name: Build with Kaniko
  run: |
    export IMAGE_TAG=${{ github.sha }}
    ./kaniko/deploy-finetuning.sh
```

---

## 📈 Monitoring

### Check Build Status

```bash
# List recent jobs
kubectl get jobs -n finetuning -l component=builder

# Check specific job
kubectl describe job kaniko-finetuning-service -n finetuning

# View logs
kubectl logs -n finetuning -l job-name=kaniko-finetuning-service

# Check image in registry
curl http://registry.kube-system.svc.cluster.local:5000/v2/finetuning-service/tags/list
```

### Build Metrics

Track build times and success rates:

```bash
# Get job completion time
kubectl get job kaniko-finetuning-service -n finetuning \
  -o jsonpath='{.status.completionTime}{"\n"}{.status.startTime}'

# Check failed builds
kubectl get jobs -n finetuning -l component=builder \
  --field-selector status.successful!=1
```

---

## 🔄 Upgrades

### Upgrading Kaniko Version

1. Check latest version: https://github.com/GoogleContainerTools/kaniko/releases
2. Update in `kaniko-job.yaml`:
   ```yaml
   image: gcr.io/kaniko-project/executor:v1.23.2  # Change version here
   ```
3. Test with a build:
   ```bash
   ./kaniko/deploy-finetuning.sh
   ```

### Migrating from Docker

If migrating from Docker-based builds:

1. Ensure Dockerfile is Kaniko-compatible (usually is)
2. Remove Docker-specific optimizations
3. Update CI/CD pipelines to use Kaniko script
4. Test thoroughly in dev environment first

---

## 📚 Additional Resources

- [Kaniko Official Docs](https://github.com/GoogleContainerTools/kaniko)
- [Kaniko Best Practices](https://github.com/GoogleContainerTools/kaniko#best-practices)
- [Dockerfile Best Practices](https://docs.docker.com/develop/develop-images/dockerfile_best-practices/)

---

## 🎓 Advanced Usage

### Multi-Architecture Builds

Currently single arch. For multi-arch:
- Use Kaniko with `--custom-platform` flag
- Or use buildx in separate workflow

### Build from Git

Can build directly from git (not recommended for this project):
```yaml
args:
  - "--context=git://github.com/user/repo"
```

### Custom Build Args

Pass build arguments:
```bash
# Edit kaniko-job.yaml
args:
  - "--build-arg=VERSION=1.0.0"
  - "--build-arg=BUILD_DATE=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
```

---

**Questions or Issues?**
Check the troubleshooting section or review the inline script documentation in `deploy-finetuning.sh`.
