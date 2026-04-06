# MinIO Helm Chart

A simple Helm chart for deploying MinIO object storage in Kubernetes.

## Prerequisites

- Kubernetes 1.19+
- Helm 3.0+
- PersistentVolume support in the underlying infrastructure (if persistence is enabled)

## Installation

### Install the chart

```bash
# From the parent directory
helm install minio ./minio-helm

# Or with custom values
helm install minio ./minio-helm -f custom-values.yaml

# Install in a specific namespace
helm install minio ./minio-helm --namespace storage --create-namespace
```

## Configuration

The following table lists the configurable parameters:

| Parameter | Description | Default |
|-----------|-------------|---------|
| `replicaCount` | Number of MinIO replicas | `1` |
| `image.repository` | MinIO image repository | `minio/minio` |
| `image.tag` | MinIO image tag | `RELEASE.2024-10-13T13-34-11Z` |
| `image.pullPolicy` | Image pull policy | `IfNotPresent` |
| `auth.rootUser` | MinIO root username | `admin` |
| `auth.rootPassword` | MinIO root password | `minio123` |
| `service.type` | Kubernetes service type | `ClusterIP` |
| `service.port` | MinIO API port | `9000` |
| `service.consolePort` | MinIO console port | `9001` |
| `persistence.enabled` | Enable persistent storage | `true` |
| `persistence.size` | Storage size | `10Gi` |
| `persistence.storageClass` | Storage class name | `""` (default) |
| `resources.limits.cpu` | CPU limit | `1000m` |
| `resources.limits.memory` | Memory limit | `2Gi` |
| `resources.requests.cpu` | CPU request | `500m` |
| `resources.requests.memory` | Memory request | `1Gi` |

## Accessing MinIO

### From within the cluster

MinIO API endpoint:
```
http://minio:9000
```

MinIO Console:
```
http://minio:9001
```

### Port forwarding for local access

```bash
# Access MinIO API
kubectl port-forward svc/minio 9000:9000

# Access MinIO Console
kubectl port-forward svc/minio 9001:9001
```

Then open http://localhost:9001 in your browser.

## Connecting from FastAPI

Update your FastAPI application to connect to MinIO:

```python
from minio import Minio

# When running in the same Kubernetes cluster
minio_client = Minio(
    "minio:9000",  # Service name and port
    access_key="admin",
    secret_key="minio123",
    secure=False  # Set to True if using HTTPS
)
```

## Uninstall

```bash
helm uninstall minio
```

## Production Considerations

For production use:
1. Change default credentials in `values.yaml`
2. Consider using Kubernetes Secrets for credentials
3. Enable HTTPS/TLS
4. Adjust resource limits based on your workload
5. Configure appropriate storage class
6. Consider deploying in distributed mode for high availability
