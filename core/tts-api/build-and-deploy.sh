#!/bin/bash
set -e

echo "🏗️  Building TTS API Docker Image..."

# Configuration
IMAGE_NAME="tts-api"
IMAGE_TAG="latest"
REGISTRY="localhost:5000"
FULL_IMAGE="${REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}"

# Build context directory
BUILD_DIR="/tmp/tts-api-build"
rm -rf "${BUILD_DIR}"
mkdir -p "${BUILD_DIR}"

echo "📦 Preparing build context..."

# Copy files to build context
cp /home/ubuntu/EI_Stack/Enterprise-Inference/core/tts-api/Dockerfile "${BUILD_DIR}/"
cp /home/ubuntu/EI_Stack/Enterprise-Inference/core/tts-api/server.py "${BUILD_DIR}/"
cp /home/ubuntu/EI_Stack/Enterprise-Inference/core/tts-api/requirements.txt "${BUILD_DIR}/"

# Copy tts_engine module
cp -r /home/ubuntu/tts_engine "${BUILD_DIR}/"

echo "🐳 Building Docker image..."
cd "${BUILD_DIR}"

# Build with containerd/nerdctl (since no Docker)
if command -v nerdctl &> /dev/null; then
    sudo nerdctl build -t "${FULL_IMAGE}" .
    echo "📤 Pushing to local registry..."
    sudo nerdctl push "${FULL_IMAGE}"
elif command -v ctr &> /dev/null; then
    # Fallback to buildkit with ctr
    sudo ctr images build -t "${FULL_IMAGE}" .
else
    echo "❌ Neither nerdctl nor ctr available. Cannot build image."
    exit 1
fi

echo "✅ Image built: ${FULL_IMAGE}"

echo "🚀 Deploying to Kubernetes..."

# Create VLLM service if it doesn't exist
if ! kubectl get svc svara-tts-vllm -n default &> /dev/null; then
    echo "📡 Creating VLLM service..."
    kubectl apply -f - <<EOF
apiVersion: v1
kind: Service
metadata:
  name: svara-tts-vllm
  namespace: default
  labels:
    app: vllm
spec:
  type: ClusterIP
  selector:
    app.kubernetes.io/name: vllm
    app.kubernetes.io/instance: svara-tts-cpu
  ports:
  - port: 2080
    targetPort: 2080
    protocol: TCP
    name: http
EOF
fi

# Apply Kubernetes manifests
kubectl apply -f /home/ubuntu/EI_Stack/Enterprise-Inference/core/tts-api/k8s-deployment.yaml

echo "⏳ Waiting for pods to be ready..."
kubectl wait --for=condition=ready pod -l app=tts-api -n tts-system --timeout=120s || true

echo ""
echo "✅ Deployment complete!"
echo ""
echo "📊 Status:"
kubectl get pods -n tts-system
echo ""
kubectl get svc -n tts-system
echo ""
echo "🔗 Access the API:"
echo "   Internal: http://tts-api.tts-system.svc.cluster.local:8000"
echo "   External: http://$(hostname -I | awk '{print $1}'):30800"
echo ""
echo "📝 Test commands:"
echo "   kubectl logs -f deployment/tts-api -n tts-system"
echo "   curl http://$(hostname -I | awk '{print $1}'):30800/health"
