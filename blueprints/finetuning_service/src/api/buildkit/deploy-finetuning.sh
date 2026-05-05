#!/bin/bash

set -e

# Get the absolute path of the finetuning-service root directory
# buildkit is 1 level deep from root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export BUILD_CONTEXT="$(cd "$SCRIPT_DIR/.." && pwd)"
export REGISTRY_URL="${REGISTRY_URL:-registry.kube-system.svc.cluster.local:5000}"
export IMAGE_TAG="${IMAGE_TAG:-latest}"
export NAMESPACE="${NAMESPACE:-finetuning}"

echo "Building with context: $BUILD_CONTEXT"
echo "Registry: $REGISTRY_URL"
echo "Image Tag: $IMAGE_TAG"
echo "Namespace: $NAMESPACE"

# Create namespace if it doesn't exist
if ! kubectl get namespace "$NAMESPACE" &> /dev/null; then
    echo "Creating namespace: $NAMESPACE"
    kubectl create namespace "$NAMESPACE"
else
    echo "Namespace $NAMESPACE already exists"
fi

# Delete old job if exists
if kubectl get job buildkit-finetuning-service -n "$NAMESPACE" >/dev/null 2>&1; then
  echo "Deleting old buildkit job..."
  kubectl delete job buildkit-finetuning-service -n "$NAMESPACE"
  sleep 2
fi

# Apply the job with substituted values using envsubst
echo "Creating BuildKit build job..."
# Pass proxy settings into the build if set in the environment
export http_proxy="${http_proxy:-}"
export https_proxy="${https_proxy:-}"
export no_proxy="${no_proxy:-}"
envsubst < "$SCRIPT_DIR/buildkit-job.yaml" | kubectl apply -f -

echo ""
echo "BuildKit job created successfully"
echo "Monitor with: kubectl logs -f job/buildkit-finetuning-service -n $NAMESPACE"
echo ""

# Wait for job to start
echo "Waiting for pod to start..."
sleep 3

# Show logs
POD_NAME=""
for i in {1..30}; do
  POD_NAME=$(kubectl get pods -n "$NAMESPACE" -l job-name=buildkit-finetuning-service -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")
  if [ -n "$POD_NAME" ]; then
    break
  fi
  sleep 1
done

if [ -n "$POD_NAME" ]; then
  echo "Following build logs..."
  echo "=========================================="
  kubectl logs -f "$POD_NAME" -n "$NAMESPACE" || true
  echo "=========================================="
  
  # Wait for job to complete and check status
  echo ""
  echo "Waiting for job to complete..."
  kubectl wait --for=condition=complete --timeout=600s job/buildkit-finetuning-service -n "$NAMESPACE" 2>/dev/null || \
  kubectl wait --for=condition=failed --timeout=10s job/buildkit-finetuning-service -n "$NAMESPACE" 2>/dev/null
  
  # Check final status
  JOB_STATUS=$(kubectl get job buildkit-finetuning-service -n "$NAMESPACE" -o jsonpath='{.status.conditions[?(@.type=="Complete")].status}' 2>/dev/null || echo "")
  JOB_FAILED=$(kubectl get job buildkit-finetuning-service -n "$NAMESPACE" -o jsonpath='{.status.conditions[?(@.type=="Failed")].status}' 2>/dev/null || echo "")
  
  if [ "$JOB_STATUS" == "True" ]; then
    echo ""
    echo "✓ Build completed successfully!"
    echo "Image: $REGISTRY_URL/finetuning-service:$IMAGE_TAG"
    echo ""
    echo "Note: Layer caching is enabled. Subsequent builds will be faster."
    exit 0
  elif [ "$JOB_FAILED" == "True" ]; then
    echo ""
    echo "✗ Build failed!"
    exit 1
  else
    echo ""
    echo "✗ Build status unknown"
    exit 1
  fi
else
  echo "Warning: Could not find pod for buildkit job"
  exit 1
fi
