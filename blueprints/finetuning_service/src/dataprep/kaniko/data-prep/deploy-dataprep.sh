#!/bin/bash

set -e

# Get the absolute path of the dataprep directory
# kaniko/data-prep is 3 levels deep from data-prep-backend root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export BUILD_CONTEXT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
export REGISTRY_URL="${REGISTRY_URL:-registry.kube-system.svc.cluster.local:5000}"

echo "Building with context: $BUILD_CONTEXT"
echo "Registry: $REGISTRY_URL"

# MinIO Configuration
export MINIO_ENDPOINT=minio.dataprep.svc.cluster.local:9000
export MINIO_ACCESS_KEY=admin
export MINIO_SECRET_KEY=minio123
export MINIO_BUCKET_NAME=dataprep
export MINIO_SECURE=false
export MINIO_REGION=us-west-2
export MINIO_CERT_VERIFY=false

# PostgreSQL Configuration
export DB_HOST=postgres.dataprep.svc.cluster.local
export DB_PORT=5432
export DB_NAME=dataprep
export DB_USER=postgres
export DB_PASSWORD=postgres
export DB_POOL_SIZE=5
export DB_MAX_OVERFLOW=10

# Copy registry-secret from kube-system to dataprep namespace if not exists
if ! kubectl get secret registry-secret -n dataprep >/dev/null 2>&1; then
  kubectl get secret registry-secret -n kube-system -o yaml \
    | sed 's/namespace: kube-system/namespace: dataprep/' \
    | kubectl apply -n dataprep -f -
  echo "registry-secret copied to dataprep namespace."
else
  echo "registry-secret already exists in dataprep namespace, skipping copy."
fi

# Apply the job with substituted values using envsubst
envsubst < "$SCRIPT_DIR/kaniko-job.yaml" | kubectl apply -f -

echo "Kaniko job created successfully"
echo "Monitor with: kubectl logs -f job/kaniko-data-prep-backend -n dataprep"
