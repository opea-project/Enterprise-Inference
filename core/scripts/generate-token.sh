#!/bin/bash

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

export BASE_URL=api.example.com # The base URL of the Keycloak server, note https:// is omitted
export KEYCLOAK_ADMIN_USERNAME=your-keycloak-admin-user # The username for Keycloak admin login
export KEYCLOAK_PASSWORD=changeme # The password for Keycloak admin login
export KEYCLOAK_CLIENT_ID=my-client-id # The client ID to be created in Keycloak

export KEYCLOAK_CLIENT_SECRET=$(bash "${SCRIPT_DIR}/keycloak-fetch-client-secret.sh" ${BASE_URL} ${KEYCLOAK_ADMIN_USERNAME} ${KEYCLOAK_PASSWORD} ${KEYCLOAK_CLIENT_ID} | awk -F': ' '/Client secret:/ {print $2}')

# Set token lifespan on the client (in seconds)
# 3600 = 1 hour, 86400 = 24 hours, 604800 = 7 days
TOKEN_LIFESPAN=${TOKEN_LIFESPAN:-3600}  # default 1 hour, override via env var

# Get admin token first
ADMIN_TOKEN=$(curl -k -s -X POST \
  https://${BASE_URL}/realms/master/protocol/openid-connect/token \
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

export TOKEN=$(curl -k -s -X POST \
  https://$BASE_URL/token \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d "grant_type=client_credentials&client_id=${KEYCLOAK_CLIENT_ID}&client_secret=${KEYCLOAK_CLIENT_SECRET}" \
  | jq -r .access_token)

echo "BASE_URL=${BASE_URL}"
echo "TOKEN=${TOKEN}"
echo "TOKEN_LIFESPAN=${TOKEN_LIFESPAN} seconds ($(( TOKEN_LIFESPAN / 60 )) minutes)"