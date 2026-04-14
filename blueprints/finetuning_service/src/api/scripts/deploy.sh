#!/bin/bash
set -e

# Get the directory where this script is located and go to project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Change to project root directory
cd "$PROJECT_ROOT"

echo "=============================================="
echo "Fine-Tuning API Deployment"
echo "=============================================="
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "❌ Error: .env file not found!"
    echo ""
    echo "Please run the setup script first:"
    echo "  ./scripts/setup.sh"
    echo ""
    echo "Or manually copy .env.example to .env and configure it"
    exit 1
fi

# Load environment variables
source .env

# Set defaults
NAMESPACE=${NAMESPACE:-finetuning}
IMAGE_TAG=${IMAGE_TAG:-latest}
BASE_DOMAIN=${BASE_DOMAIN:-example.com}
CERTS_PATH=${CERTS_PATH:-/home/ubuntu/certs}

# Validate required variables
echo "🔍 Validating configuration..."
MISSING_VARS=()

if [ -z "$NVIDIA_API_URL" ] || [ "$NVIDIA_API_URL" = "https://your-training-backend.example.com:8443" ]; then
    MISSING_VARS+=("NVIDIA_API_URL")
fi
if [ -z "$NVIDIA_API_KEY" ] || [ "$NVIDIA_API_KEY" = "your_nvidia_api_key_here" ]; then
    MISSING_VARS+=("NVIDIA_API_KEY")
fi
if [ -z "$BASE_DOMAIN" ] || [ "$BASE_DOMAIN" = "example.com" ]; then
    MISSING_VARS+=("BASE_DOMAIN")
fi
if [ -z "$POSTGRES_PASSWORD" ] || [ "$POSTGRES_PASSWORD" = "AUTO_GENERATED_PASSWORD" ]; then
    MISSING_VARS+=("POSTGRES_PASSWORD (run setup.sh to auto-generate)")
fi

if [ ${#MISSING_VARS[@]} -ne 0 ]; then
    echo "❌ The following required variables are not configured:"
    for var in "${MISSING_VARS[@]}"; do
        echo "   - $var"
    done
    echo ""
    echo "Please run ./setup.sh to configure automatically,"
    echo "or edit .env file manually."
    exit 1
fi

echo "✓ Configuration validated"
echo ""
echo "📋 Deployment Summary:"
echo "  • Namespace: $NAMESPACE"
echo "  • Domain: $BASE_DOMAIN"
  echo "  • API URL: https://$BASE_DOMAIN/training"
echo "  • Image Tag: $IMAGE_TAG"
echo "  • Training Backend: $NVIDIA_API_URL"
echo ""

# Create namespace
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📦 Step 1: Creating namespace..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
kubectl create namespace $NAMESPACE --dry-run=client -o yaml | kubectl apply -f -
echo "✓ Namespace ready"
echo ""

# Copy OIDC secret from default namespace if it exists
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔐 Step 2: Copying OIDC secret..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if kubectl get secret finetuning-backend-secret -n default >/dev/null 2>&1; then
  kubectl get secret finetuning-backend-secret -n default -o yaml \
    | sed "s/namespace: default/namespace: $NAMESPACE/" \
    | kubectl apply -n $NAMESPACE -f -
  echo "✓ OIDC secret copied from default namespace"
else
  echo "⚠️  Warning: finetuning-backend-secret not found in default namespace"
  echo "   OIDC authentication will not work until secret is created"
fi
echo ""

# Create TLS secret from certs folder
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔐 Step 2: Setting up TLS certificates..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Path to certs folder from environment variable or default
CERTS_DIR="${CERTS_PATH:-../certs}"

if [ ! -d "$CERTS_DIR" ]; then
    echo "⚠️  Warning: Certs directory not found at $CERTS_DIR"
    echo "   Expected TLS certificates in certs folder:"
    echo "   - tls.crt (certificate)"
    echo "   - tls.key (private key)"
    echo ""
    echo "   Continuing without TLS setup..."
else
    # Find certificate and key files
    CERT_FILE=""
    KEY_FILE=""

    # Look for common certificate file names
    for cert in "$CERTS_DIR/tls.crt" "$CERTS_DIR/cert.pem" "$CERTS_DIR/*.crt" "$CERTS_DIR/fullchain.pem"; do
        if [ -f "$cert" ]; then
            CERT_FILE="$cert"
            break
        fi
    done

    # Look for common key file names
    for key in "$CERTS_DIR/tls.key" "$CERTS_DIR/key.pem" "$CERTS_DIR/*.key" "$CERTS_DIR/privkey.pem"; do
        if [ -f "$key" ]; then
            KEY_FILE="$key"
            break
        fi
    done

    if [ -z "$CERT_FILE" ] || [ -z "$KEY_FILE" ]; then
        echo "⚠️  Warning: Certificate or key file not found in $CERTS_DIR"
        echo "   Expected files: tls.crt and tls.key (or similar)"
        echo "   Found files:"
        ls -la "$CERTS_DIR/" 2>/dev/null || echo "   (directory empty)"
        echo ""
        echo "   Continuing without TLS setup..."
    else
        echo "Found certificate: $CERT_FILE"
        echo "Found key: $KEY_FILE"

        # Check if secret already exists
        if kubectl get secret finetuning-api-tls -n $NAMESPACE >/dev/null 2>&1; then
            echo "Updating existing TLS secret..."
            kubectl delete secret finetuning-api-tls -n $NAMESPACE
        else
            echo "Creating new TLS secret..."
        fi

        kubectl create secret tls finetuning-api-tls \
            --cert="$CERT_FILE" \
            --key="$KEY_FILE" \
            -n $NAMESPACE

        echo "✓ TLS secret created successfully"
    fi
fi
echo ""

# Build Docker image with Kaniko
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔨 Step 3: Building Docker image with Kaniko..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Export variables for kaniko script
export NAMESPACE=$NAMESPACE
export IMAGE_TAG=$IMAGE_TAG
export REGISTRY_URL="${REGISTRY_URL:-registry.kube-system.svc.cluster.local:5000}"

# Run kaniko build
if [ -f ./kaniko/deploy-finetuning.sh ]; then
    echo "Building image: $REGISTRY_URL/finetuning-service:$IMAGE_TAG"
    ./kaniko/deploy-finetuning.sh
    if [ $? -ne 0 ]; then
        echo "❌ Build failed!"
        exit 1
    fi
    echo "✓ Image built successfully"
else
    echo "⚠️  Warning: kaniko/deploy-finetuning.sh not found, skipping build"
fi
echo ""

# Deploy using Helm
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🚀 Step 3: Deploying PostgreSQL..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Check if PostgreSQL release exists
if helm list -n $NAMESPACE | grep -q "^finetuning-service-postgresql\s"; then
    echo "Upgrading existing PostgreSQL..."
    HELM_PG_CMD="upgrade"
else
    echo "Installing new PostgreSQL..."
    HELM_PG_CMD="install"
fi

# Deploy PostgreSQL
helm $HELM_PG_CMD finetuning-service-postgresql ./helm-charts/postgresql \
  --namespace $NAMESPACE \
  --set auth.password="$POSTGRES_PASSWORD" \
  --wait --timeout 5m

echo "✓ PostgreSQL deployment complete"
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🚀 Step 4: Deploying Application..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Check if release exists
if helm list -n $NAMESPACE | grep -q "^finetuning-service\s"; then
    echo "Upgrading existing deployment..."
    HELM_CMD="upgrade"
else
    echo "Installing new deployment..."
    HELM_CMD="install"
fi

# Deploy with Helm
helm $HELM_CMD finetuning-service ./helm-charts/finetuning-api \
  --namespace $NAMESPACE \
  --set secrets.databaseUrl="postgresql://finetuning:$POSTGRES_PASSWORD@finetuning-service-postgresql:5432/finetuning" \
  --set secrets.nvidiaApiKey="$NVIDIA_API_KEY" \
  --set app.config.nvidiaApiUrl="$NVIDIA_API_URL" \
  --set ingress.baseDomain="$BASE_DOMAIN" \
  --set app.image.tag="$IMAGE_TAG" \
  --wait --timeout 10m

echo "✓ Helm deployment complete"
echo ""

# Initialize database if needed
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🗄️  Step 5: Checking database initialization..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Wait for PostgreSQL to be ready
echo "Waiting for PostgreSQL..."
kubectl wait --for=condition=ready pod \
  -l app=postgres \
  -n $NAMESPACE \
  --timeout=300s || true

# Check if database is initialized
POD_NAME=$(kubectl get pods -n $NAMESPACE -l app=postgres -o jsonpath='{.items[0].metadata.name}')
if [ ! -z "$POD_NAME" ]; then
    echo "Checking database schema..."
    TABLE_COUNT=$(kubectl exec -n $NAMESPACE $POD_NAME -- psql -U finetuning -d finetuning -tAc "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public';" 2>/dev/null || echo "0")

    if [ "$TABLE_COUNT" = "0" ]; then
        echo "Initializing database schema..."
        cat "$PROJECT_ROOT/init-db.sql" | kubectl exec -n $NAMESPACE -i $POD_NAME -- psql -U finetuning -d finetuning
        echo "✓ Database initialized"
    else
        echo "✓ Database already initialized ($TABLE_COUNT tables found)"
    fi
else
    echo "⚠️  Warning: PostgreSQL pod not found. Database initialization skipped."
fi
echo ""

# Wait for application deployment
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "⏳ Step 6: Waiting for application to be ready..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
kubectl rollout status deployment/finetuning-service -n $NAMESPACE --timeout=5m

echo "✓ Application is ready"
echo ""

# Show deployment status
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 Deployment Status"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
kubectl get pods -n $NAMESPACE
echo ""
kubectl get ingress -n $NAMESPACE
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Deployment Complete!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "🌐 API URL: https://$BASE_DOMAIN/enterprise-ai"
echo ""
echo "🌐 API Docs: https://$BASE_DOMAIN/enterprise-ai/api/docs"
echo ""
echo "📝 Useful Commands:"
echo ""
echo "  Check pod status:"
echo "    kubectl get pods -n $NAMESPACE"
echo ""
echo "  View application logs:"
echo "    kubectl logs -f deployment/finetuning-service -n $NAMESPACE"
echo ""
echo "  View PostgreSQL logs:"
echo "    kubectl logs -f $POD_NAME -n $NAMESPACE"
echo ""
echo "  Access the API:"
echo "    curl https://$BASE_DOMAIN/enterprise-ai/api/health"
echo ""
echo "  Port-forward for local testing:"
echo "    kubectl port-forward -n $NAMESPACE svc/finetuning-service 8000:8000"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
