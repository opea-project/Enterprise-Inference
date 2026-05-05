#!/bin/bash
set -e
#sudo apt-get install gettext-base
# Get the absolute path of the ui directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export BUILD_CONTEXT="$(cd "$SCRIPT_DIR/../.." && pwd)"
export REGISTRY_URL="${REGISTRY_URL:-registry.kube-system.svc.cluster.local:5000}"

echo "Building with context: $BUILD_CONTEXT"
echo "Registry: $REGISTRY_URL"

export NEXT_PUBLIC_AUTH_URL="${NEXT_PUBLIC_AUTH_URL:-}"
export NEXT_PUBLIC_BASE_PATH="${NEXT_PUBLIC_BASE_PATH:-/enterprise-ai/ui}"
export NEXT_PUBLIC_FILES_BASE_URL="${NEXT_PUBLIC_FILES_BASE_URL:-}"
export NEXT_PUBLIC_DATAPREP_BASE_URL="${NEXT_PUBLIC_DATAPREP_BASE_URL:-}"
export NEXT_PUBLIC_FINETUNING_API_URL="${NEXT_PUBLIC_FINETUNING_API_URL:-}"
export NEXT_PUBLIC_DEPLOYMENT_API_URL="${NEXT_PUBLIC_DEPLOYMENT_API_URL:-}"
export NEXT_TELEMETRY_DISABLED="${NEXT_TELEMETRY_DISABLED:-1}"

# Delete old job if exists
if kubectl get job kaniko-frontend -n "${NAMESPACE:-finetuning-ui}" >/dev/null 2>&1; then
  echo "Deleting old kaniko job..."
  kubectl delete job kaniko-frontend -n "${NAMESPACE:-finetuning-ui}"
fi

# Apply the job with substituted values using envsubst
echo "Creating Kaniko build job..."
envsubst < "$SCRIPT_DIR/kaniko-job.yaml" | kubectl apply -f -

echo "Kaniko job created successfully"
echo "Monitor with: kubectl logs -f job/kaniko-frontend -n ${NAMESPACE:-finetuning-ui}"

# Wait for pod to start
echo "Waiting for kaniko pod to start..."
for i in $(seq 1 60); do
  POD_NAME=$(kubectl get pods -n "${NAMESPACE:-finetuning-ui}" -l job-name=kaniko-frontend -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")
  if [ -n "$POD_NAME" ]; then
    echo "Pod started: $POD_NAME"
    kubectl logs -f "$POD_NAME" -n "${NAMESPACE:-finetuning-ui}" || true
    break
  fi
  sleep 5
done

# Wait for job to complete
echo "Waiting for job to complete..."
kubectl wait --for=condition=complete --timeout=600s job/kaniko-frontend -n "${NAMESPACE:-finetuning-ui}" 2>/dev/null || \
kubectl wait --for=condition=failed --timeout=10s job/kaniko-frontend -n "${NAMESPACE:-finetuning-ui}" 2>/dev/null

JOB_STATUS=$(kubectl get job kaniko-frontend -n "${NAMESPACE:-finetuning-ui}" -o jsonpath='{.status.conditions[?(@.type=="Complete")].status}' 2>/dev/null || echo "")
JOB_FAILED=$(kubectl get job kaniko-frontend -n "${NAMESPACE:-finetuning-ui}" -o jsonpath='{.status.conditions[?(@.type=="Failed")].status}' 2>/dev/null || echo "")

if [ "$JOB_STATUS" = "True" ]; then
  echo "✓ UI image build completed successfully!"
elif [ "$JOB_FAILED" = "True" ]; then
  echo "✗ UI image build failed!"
  exit 1
else
  echo "Warning: Could not determine job completion status"
fi