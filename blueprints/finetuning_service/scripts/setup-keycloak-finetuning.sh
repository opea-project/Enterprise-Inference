#!/bin/bash

# Copyright (C) 2025-2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

# This script sets up Keycloak realm and clients for Fine-Tuning Platform
#
# Usage:
# ./setup-keycloak-finetuning.sh
#
# This script will:
# 1. Create 'finetuning' realm
# 2. Create 'finetuning-backend' confidential client (for API/DataPrep backend verification)
# 3. Create 'finetuning-ui' public client (for UI authentication)
# 4. Configure clients with proper redirect URIs and settings

set -e

# Get Keycloak URL from kubectl
KEYCLOAK_SERVICE=$(kubectl get svc -n default -l app.kubernetes.io/name=keycloak -o jsonpath='{.items[0].metadata.name}')
KEYCLOAK_PORT=$(kubectl get svc -n default ${KEYCLOAK_SERVICE} -o jsonpath='{.spec.ports[?(@.name=="http")].port}')
KEYCLOAK_URL="http://${KEYCLOAK_SERVICE}.default.svc.cluster.local:${KEYCLOAK_PORT}"

# Get admin credentials from inference config
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INFERENCE_CONFIG="${SCRIPT_DIR}/../../../core/inventory/inference-config.cfg"
KEYCLOAK_ADMIN=$(grep "^keycloak_admin_user=" "$INFERENCE_CONFIG" | cut -d'=' -f2)
KEYCLOAK_ADMIN_PASSWORD=$(grep "^keycloak_admin_password=" "$INFERENCE_CONFIG" | cut -d'=' -f2)

# Get cluster URL for redirect URIs
CLUSTER_URL=$(kubectl get cm -n default cluster-config -o jsonpath='{.data.cluster_url}' 2>/dev/null || echo "")

echo "========================================="
echo "Keycloak Fine-Tuning Setup"
echo "========================================="
echo "Keycloak URL: $KEYCLOAK_URL"
echo "Cluster URL: $CLUSTER_URL"
echo "Realm: finetuning"
echo "========================================="

# Login to Keycloak
echo "Logging in to Keycloak..."
TOKEN=$(curl -s -X POST "$KEYCLOAK_URL/realms/master/protocol/openid-connect/token" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "username=$KEYCLOAK_ADMIN" \
    -d "password=$KEYCLOAK_ADMIN_PASSWORD" \
    -d 'grant_type=password' \
    -d 'client_id=admin-cli' | jq -r '.access_token')

if [ -z "$TOKEN" ] || [ "$TOKEN" == "null" ]; then
    echo "❌ Login failed"
    exit 1
fi
echo "✓ Logged in successfully"

# Create finetuning realm
echo "Creating 'finetuning' realm..."
REALM_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$KEYCLOAK_URL/admin/realms" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    -d '{
        "realm": "finetuning",
        "enabled": true,
        "displayName": "Fine-Tuning Platform",
        "accessTokenLifespan": 900
    }')

HTTP_CODE=$(echo "$REALM_RESPONSE" | tail -n1)
RESPONSE_BODY=$(echo "$REALM_RESPONSE" | sed '$d')

if [ "$HTTP_CODE" == "201" ]; then
    echo "✓ Realm 'finetuning' created successfully"
elif echo "$RESPONSE_BODY" | grep -q "Conflict detected"; then
    echo "✓ Realm 'finetuning' already exists"
else
    echo "❌ Failed to create realm: $RESPONSE_BODY"
    exit 1
fi

# Create finetuning-backend client (confidential - for backend token verification)
echo "Creating 'finetuning-backend' confidential client..."
BACKEND_CLIENT_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$KEYCLOAK_URL/admin/realms/finetuning/clients" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    -d '{
        "clientId": "finetuning-backend",
        "name": "Fine-Tuning Backend Service",
        "description": "Backend service for API and DataPrep token verification",
        "protocol": "openid-connect",
        "publicClient": false,
        "serviceAccountsEnabled": true,
        "directAccessGrantsEnabled": true,
        "standardFlowEnabled": false,
        "implicitFlowEnabled": false,
        "authorizationServicesEnabled": false
    }')

HTTP_CODE=$(echo "$BACKEND_CLIENT_RESPONSE" | tail -n1)
RESPONSE_BODY=$(echo "$BACKEND_CLIENT_RESPONSE" | sed '$d')

if [ "$HTTP_CODE" == "201" ]; then
    echo "✓ Client 'finetuning-backend' created successfully"
elif echo "$RESPONSE_BODY" | grep -q "already exists"; then
    echo "✓ Client 'finetuning-backend' already exists"
else
    echo "❌ Failed to create backend client: $RESPONSE_BODY"
fi

# Get finetuning-backend client UUID and secret
BACKEND_CLIENT_UUID=$(curl -s -X GET "$KEYCLOAK_URL/admin/realms/finetuning/clients?clientId=finetuning-backend" \
    -H "Authorization: Bearer $TOKEN" | jq -r '.[0].id')

if [ -n "$BACKEND_CLIENT_UUID" ] && [ "$BACKEND_CLIENT_UUID" != "null" ]; then
    BACKEND_CLIENT_SECRET=$(curl -s -X GET "$KEYCLOAK_URL/admin/realms/finetuning/clients/$BACKEND_CLIENT_UUID/client-secret" \
        -H "Authorization: Bearer $TOKEN" | jq -r '.value')
    echo "✓ Backend Client Secret: $BACKEND_CLIENT_SECRET"
fi

# Create finetuning-ui client (public - for UI authentication)
echo "Creating 'finetuning-ui' public client..."
UI_CLIENT_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$KEYCLOAK_URL/admin/realms/finetuning/clients" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    -d "{
        \"clientId\": \"finetuning-ui\",
        \"name\": \"Fine-Tuning UI\",
        \"description\": \"Public client for Fine-Tuning UI authentication\",
        \"protocol\": \"openid-connect\",
        \"publicClient\": true,
        \"serviceAccountsEnabled\": false,
        \"directAccessGrantsEnabled\": false,
        \"standardFlowEnabled\": true,
        \"implicitFlowEnabled\": false,
        \"redirectUris\": [
            \"https://${CLUSTER_URL}/finetune/ui/*\",
            \"https://${CLUSTER_URL}/finetune/ui/api/auth/callback/keycloak\",
            \"http://localhost:3000/*\",
            \"http://localhost:3000/api/auth/callback/keycloak\"
        ],
        \"webOrigins\": [
            \"https://${CLUSTER_URL}\",
            \"http://localhost:3000\"
        ],
        \"attributes\": {
            \"pkce.code.challenge.method\": \"S256\"
        }
    }")

HTTP_CODE=$(echo "$UI_CLIENT_RESPONSE" | tail -n1)
RESPONSE_BODY=$(echo "$UI_CLIENT_RESPONSE" | sed '$d')

if [ "$HTTP_CODE" == "201" ]; then
    echo "✓ Client 'finetuning-ui' created successfully"
elif echo "$RESPONSE_BODY" | grep -q "already exists"; then
    echo "✓ Client 'finetuning-ui' already exists"
else
    echo "❌ Failed to create UI client: $RESPONSE_BODY"
fi

echo "========================================="
echo "✓ Keycloak Setup Complete!"
echo "========================================="
echo "Realm: finetuning"
echo "Backend Client ID: finetuning-backend"
echo "Backend Client Secret: $BACKEND_CLIENT_SECRET"
echo "UI Client ID: finetuning-ui (public client - no secret)"
echo "Keycloak Issuer: $KEYCLOAK_URL/realms/finetuning"
echo "========================================="
echo ""
echo "Save these credentials in your config:"
echo "  finetune_keycloak_url: $KEYCLOAK_URL"
echo "  finetune_keycloak_realm: finetuning"
echo "  finetune_keycloak_backend_client_id: finetuning-backend"
echo "  finetune_keycloak_backend_client_secret: $BACKEND_CLIENT_SECRET"
echo "  finetune_keycloak_ui_client_id: finetuning-ui"
echo "========================================="
