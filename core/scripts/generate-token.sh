#!/bin/bash

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

export KEYCLOAK_URL=api.example.com # The base URL of the Keycloak server, note https:// is omitted
export KEYCLOAK_ADMIN_USERNAME=your-keycloak-admin-user # The username for Keycloak admin login
export KEYCLOAK_PASSWORD=changeme # The password for Keycloak admin login
export KEYCLOAK_CLIENT_ID=my-client-id # The client ID to be created in Keycloak

export KEYCLOAK_CLIENT_SECRET=$(bash "${SCRIPT_DIR}/keycloak-fetch-client-secret.sh" ${KEYCLOAK_URL} ${KEYCLOAK_ADMIN_USERNAME} ${KEYCLOAK_PASSWORD} ${KEYCLOAK_CLIENT_ID} | awk -F': ' '/Client secret:/ {print $2}')
export TOKEN=$(curl -k -X POST https://$KEYCLOAK_URL/token  -H 'Content-Type: application/x-www-form-urlencoded' -d "grant_type=client_credentials&client_id=${KEYCLOAK_CLIENT_ID}&client_secret=${KEYCLOAK_CLIENT_SECRET}" | jq -r .access_token)
echo "TOKEN=${TOKEN}"
