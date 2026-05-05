# Redis Helm Chart

This chart deploys a Redis instance on Kubernetes with persistent storage.

## Files
- `Chart.yaml`: Chart metadata
- `values.yaml`: Configurable values (replicas, image, service, persistence)
- `templates/deployment.yaml`: Redis Deployment
- `templates/service.yaml`: Redis Service
- `templates/pvc.yaml`: PersistentVolumeClaim for Redis data
- `templates/_helpers.tpl`: Template helpers

## Usage

```bash
helm install my-redis ./redis-helm
```

## Configuration
Edit `values.yaml` to customize replica count, image, service type, and storage.
