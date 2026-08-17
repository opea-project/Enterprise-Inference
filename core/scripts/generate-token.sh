#!/bin/bash
# Copyright (C) 2025-2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Override any of these via the environment instead of editing this file, e.g.
#   KEYCLOAK_PASSWORD='...' ./generate-token.sh
export BASE_URL="${BASE_URL:-api.example.com}"                                  # Keycloak server base URL, https:// omitted
export KEYCLOAK_ADMIN_USERNAME="${KEYCLOAK_ADMIN_USERNAME:-your-keycloak-admin-user}"  # Keycloak admin username
export KEYCLOAK_PASSWORD="${KEYCLOAK_PASSWORD:?Set KEYCLOAK_PASSWORD in the environment}"  # Keycloak admin password
export KEYCLOAK_CLIENT_ID="${KEYCLOAK_CLIENT_ID:-my-client-id}"                 # Client ID to create in Keycloak

KEYCLOAK_CLIENT_SECRET=$(bash "${SCRIPT_DIR}/keycloak-fetch-client-secret.sh" "${BASE_URL}" "${KEYCLOAK_ADMIN_USERNAME}" "${KEYCLOAK_PASSWORD}" "${KEYCLOAK_CLIENT_ID}" | awk -F': ' '/Client secret:/ {print $2}')
export KEYCLOAK_CLIENT_SECRET

# Set token lifespan on the client (in seconds)
# 3600 = 1 hour, 86400 = 24 hours, 604800 = 7 days
TOKEN_LIFESPAN=${TOKEN_LIFESPAN:-3600}  # default 1 hour, override via env var

# Get admin token first
ADMIN_TOKEN=$(curl -k -s -X POST \
  "https://${BASE_URL}/realms/master/protocol/openid-connect/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=password" \
  -d "client_id=admin-cli" \
  -d "username=${KEYCLOAK_ADMIN_USERNAME}" \
  -d "password=${KEYCLOAK_PASSWORD}" | jq -r '.access_token')

# Get the client UUID
CLIENT_UUID=$(curl -k -s \
  "https://${BASE_URL}/admin/realms/master/clients?clientId=${KEYCLOAK_CLIENT_ID}" \
  -H "Authorization: Bearer ${ADMIN_TOKEN}" | jq -r '.[0].id')

# Update token lifespan for the client
curl -k -s -X PUT \
  "https://${BASE_URL}/admin/realms/master/clients/${CLIENT_UUID}" \
  -H "Authorization: Bearer ${ADMIN_TOKEN}" \
  -H "Content-Type: application/json" \
  -d "{\"attributes\": {\"access.token.lifespan\": \"${TOKEN_LIFESPAN}\"}}"

TOKEN=$(curl -k -s -X POST \
  "https://${BASE_URL}/token" \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d "grant_type=client_credentials&client_id=${KEYCLOAK_CLIENT_ID}&client_secret=${KEYCLOAK_CLIENT_SECRET}" \
  | jq -r .access_token)
export TOKEN

echo "BASE_URL=${BASE_URL}"
echo "TOKEN=${TOKEN}"
echo "TOKEN_LIFESPAN=${TOKEN_LIFESPAN} seconds ($(( TOKEN_LIFESPAN / 60 )) minutes)"