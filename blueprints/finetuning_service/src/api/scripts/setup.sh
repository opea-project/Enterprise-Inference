#!/bin/bash
set -e

# Get the directory where this script is located and go to project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Change to project root directory
cd "$PROJECT_ROOT"

echo "=============================================="
echo "Fine-Tuning API - Initial Setup"
echo "=============================================="
echo ""
echo "This script will help you configure the Fine-Tuning API."
echo "I'll auto-generate all passwords and secrets for you."
echo "You only need to provide information about your external services."
echo ""

# Check if .env already exists
if [ -f .env ]; then
    echo "⚠️  .env file already exists!"
    read -p "Do you want to overwrite it? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Setup cancelled. Existing .env file kept."
        exit 0
    fi
fi

# Function to generate a secure password
generate_password() {
    openssl rand -base64 32 | tr -d "=+/" | cut -c1-32
}

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📝 Step 1: External Services Configuration"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Training Backend Configuration (Nvidia/Unsloth)
echo "🎯 Training Backend Configuration"
echo "This is the URL of your training backend service (e.g., Nvidia GPU server)."
echo ""
read -p "Training Backend URL (e.g., https://training.example.com:8443): " NVIDIA_API_URL
while [ -z "$NVIDIA_API_URL" ]; do
    echo "❌ Training Backend URL is required!"
    read -p "Training Backend URL: " NVIDIA_API_URL
done

echo ""
read -p "Training Backend API Key: " NVIDIA_API_KEY
while [ -z "$NVIDIA_API_KEY" ]; do
    echo "❌ Training Backend API Key is required!"
    read -p "Training Backend API Key: " NVIDIA_API_KEY
done

# Domain Configuration
echo ""
echo "🌐 Domain Configuration"
echo "The API will be accessible at: https://YOUR_DOMAIN/enterprise-ai"
echo ""
read -p "Your domain name (e.g., example.com): " BASE_DOMAIN
while [ -z "$BASE_DOMAIN" ]; do
    echo "❌ Domain name is required!"
    read -p "Your domain name: " BASE_DOMAIN
done

# TLS Certificates Path
echo ""
echo "🔒 TLS Certificates Configuration"
echo "Provide the path to directory containing your TLS certificates."
echo "Expected files: tls.crt (or cert.pem) and tls.key (or key.pem)"
echo ""
read -p "Path to certs directory (default: ../certs): " CERTS_PATH
CERTS_PATH=${CERTS_PATH:-../certs}

# Validate certs path
if [ ! -d "$CERTS_PATH" ]; then
    echo "⚠️  Warning: Directory '$CERTS_PATH' not found!"
    echo "   Make sure to create it and add your certificates before deploying."
fi

# Namespace
echo ""
read -p "Kubernetes namespace (default: finetuning): " NAMESPACE
NAMESPACE=${NAMESPACE:-finetuning}

# Optional: Dataprep API
echo ""
echo "🔧 Optional: Dataprep API"
echo "If you have a separate dataprep service, provide the URL. Otherwise, leave empty."
read -p "Dataprep API URL (optional, press Enter to skip): " DATAPREP_API_URL

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔐 Step 2: Auto-generating Secure Passwords"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Generating secure passwords for internal services..."

# Generate passwords
POSTGRES_PASSWORD=$(generate_password)

echo "✓ PostgreSQL password generated"

# Construct DATABASE_URL
DATABASE_URL="postgresql://finetuning:${POSTGRES_PASSWORD}@finetuning-service-postgresql:5432/finetuning"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "💾 Step 3: Saving Configuration"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Create .env file
cat > .env << EOF
# ============================================
# Fine-Tuning API Configuration
# Auto-generated on $(date)
# ============================================

# ============================================
# DATABASE CONFIGURATION (Auto-generated)
# ============================================
DATABASE_URL=${DATABASE_URL}
DB_POOL_MIN_SIZE=5
DB_POOL_MAX_SIZE=20

# ============================================
# TRAINING BACKEND CONFIGURATION (User-provided)
# ============================================
NVIDIA_API_URL=${NVIDIA_API_URL}
NVIDIA_API_KEY=${NVIDIA_API_KEY}
NVIDIA_API_TIMEOUT=120
NVIDIA_MAX_JOBS=1

# ============================================
# OPTIONAL SERVICES
# ============================================
DATAPREP_API_URL=${DATAPREP_API_URL}

# ============================================
# DEPLOYMENT CONFIGURATION
# ============================================
NAMESPACE=${NAMESPACE}
BASE_DOMAIN=${BASE_DOMAIN}
IMAGE_TAG=latest
CERTS_PATH=${CERTS_PATH}

# ============================================
# SERVER CONFIGURATION
# ============================================
SERVER_HOST=0.0.0.0
SERVER_PORT=8000
LOG_LEVEL=INFO
CORS_ORIGINS=["*"]
CORS_ALLOW_CREDENTIALS=true

# ============================================
# INTERNAL USE (Auto-generated)
# ============================================
POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
EOF

echo "✓ Configuration saved to .env"

# Update values.yaml with domain
echo ""
echo "Updating helm-charts/finetuning-api/values.yaml with your domain..."

# Use sed to update the baseDomain in values.yaml
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    sed -i '' "s/baseDomain: \".*\"/baseDomain: \"${BASE_DOMAIN}\"/" helm-charts/finetuning-api/values.yaml
else
    # Linux
    sed -i "s/baseDomain: \".*\"/baseDomain: \"${BASE_DOMAIN}\"/" helm-charts/finetuning-api/values.yaml
fi

echo "✓ Domain updated in helm-charts/finetuning-api/values.yaml"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Setup Complete!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📋 Summary:"
echo "  • Configuration saved to: .env"
echo "  • Domain configured: ${BASE_DOMAIN}"
  echo "  • API will be at: https://${BASE_DOMAIN}/enterprise-ai"
echo "  • Namespace: ${NAMESPACE}"
echo ""
echo "🚀 Next Steps:"
echo ""
echo "  1. Review the .env file to verify all settings"
echo "  2. Deploy the application:"
echo "     ./deploy.sh"
echo ""
echo "  3. After deployment, access the API at:"
echo "     https://${BASE_DOMAIN}/enterprise-ai"
echo ""
echo "  4. Check deployment status:"
echo "     kubectl get pods -n ${NAMESPACE}"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "⚠️  IMPORTANT: The .env file contains sensitive passwords."
echo "   • Never commit it to git (it's in .gitignore)"
echo "   • Keep it secure and backed up safely"
echo ""
