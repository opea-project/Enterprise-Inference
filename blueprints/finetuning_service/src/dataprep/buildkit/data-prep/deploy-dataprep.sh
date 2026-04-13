#!/bin/bash

set -e

# Get the absolute path of the dataprep directory
# buildkit/data-prep is 3 levels deep from data-prep-backend root
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

# Delete old job if exists
kubectl delete job buildkit-data-prep-backend -n dataprep --ignore-not-found=true

# Pass proxy settings into the build if set in the environment
export http_proxy="${http_proxy:-}"
export https_proxy="${https_proxy:-}"
export no_proxy="${no_proxy:-}"

# Apply the job with substituted values using envsubst
envsubst < "$SCRIPT_DIR/buildkit-job.yaml" | kubectl apply -f -

echo "BuildKit job created successfully"
echo "Monitor with: kubectl logs -f job/buildkit-data-prep-backend -n dataprep"
