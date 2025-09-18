#!/bin/bash
set -e

# Function to generate secure passwords
generate_password() {
    local length=${1:-16}
    openssl rand -base64 $((length * 3 / 4)) | tr -d "=+/" | cut -c1-$length
}

# Function to generate hex keys
generate_hex_key() {
    local length=${1:-32}
    openssl rand -hex $length
}

echo "🔧 Generating secure credentials..."

# Generate secure individual vault secrets
LITELLM_MASTER_KEY="sk-$(generate_hex_key 10)"
LITELLM_SALT_KEY=$(generate_hex_key 10)
REDIS_PASSWORD=$(generate_password 20)
LANGFUSE_SECRET_KEY="lf_sk_$(generate_hex_key 10)"
LANGFUSE_PUBLIC_KEY="lf_pk_$(generate_hex_key 10)"
POSTGRESQL_USERNAME="admin"
POSTGRESQL_PASSWORD=$(generate_password 20)
CLICKHOUSE_USERNAME="default"
CLICKHOUSE_PASSWORD=$(generate_password 20)
LANGFUSE_LOGIN="admin@admin.com"
LANGFUSE_USER="admin"
LANGFUSE_PASSWORD="Admin$(generate_password 20)!"
MINIO_USER="minio"
MINIO_SECRET=$(generate_password 20)
POSTGRES_USER="postgres"
POSTGRES_PASSWORD=$(generate_password 20)

# Generate connection strings
DATABASE_URL="postgresql://admin:${POSTGRESQL_PASSWORD}@genai-gateway-postgresql:5432/litellm"
CLICKHOUSE_REDIS_URL="redis://default:${CLICKHOUSE_PASSWORD}@genai-gateway-trace-valkey-primary:6379/0"

echo "Generated secure credentials!"
echo ""

# Create target directory if it doesn't exist
VAULT_DIR="${VAULT_DIR:-$(realpath "$(dirname "${BASH_SOURCE[0]}")/../inventory/metadata")}"

# Create vault.yml file
VAULT_FILE="$VAULT_DIR/vault.yml"
echo "Creating vault.yml file at: $VAULT_FILE"

cat > "$VAULT_FILE" << EOF
# Auto-generated Individual Vault Secrets
litellm_master_key: "$LITELLM_MASTER_KEY"
litellm_salt_key: "$LITELLM_SALT_KEY"
redis_password: "$REDIS_PASSWORD"
langfuse_secret_key: "$LANGFUSE_SECRET_KEY"
langfuse_public_key: "$LANGFUSE_PUBLIC_KEY"
postgresql_username: "$POSTGRESQL_USERNAME"
postgresql_password: "$POSTGRESQL_PASSWORD"
clickhouse_username: "$CLICKHOUSE_USERNAME"
clickhouse_password: "$CLICKHOUSE_PASSWORD"
langfuse_login: "$LANGFUSE_LOGIN"
langfuse_user: "$LANGFUSE_USER"
langfuse_password: "$LANGFUSE_PASSWORD"
minio_secret: "$MINIO_SECRET"
minio_user: "$MINIO_USER"
postgres_user: "$POSTGRES_USER"
postgres_password: "$POSTGRES_PASSWORD"
EOF

# Set appropriate permissions
chmod 640 "$VAULT_FILE"