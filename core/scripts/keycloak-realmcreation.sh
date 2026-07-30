#!/bin/bash

# Copyright (C) 2025-2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
# Permission is granted for recipient to internally use and modify this software for purposes of benchmarking and testing on Intel architectures. 
# This software is provided "AS IS" possibly with faults, bugs or errors; it is not intended for production use, and recipient uses this design at their own risk with no liability to Intel.
# Intel disclaims all warranties, express or implied, including warranties of merchantability, fitness for a particular purpose, and non-infringement. 
# Recipient agrees that any feedback it provides to Intel about this software is licensed to Intel for any purpose worldwide. No permission is granted to use Intel’s trademarks.
# The above copyright notice and this permission notice shall be included in all copies or substantial portions of the code.



# This script automates the creation and configuration of a Keycloak client.
#
# Usage:
# ./keycloak-realmcreation.sh <KEYCLOAK_HOST>
#
# Arguments:
#   KEYCLOAK_HOST - The host[:port] of the Keycloak server (no scheme).
#
# Credentials are read from the environment (positional args 2-4 are accepted
# as a fallback):
#   KEYCLOAK_ADMIN_USER     - The username for Keycloak admin login.
#   KEYCLOAK_ADMIN_PASSWORD - The password for Keycloak admin login.
#   KEYCLOAK_CLIENT_ID      - The client ID to be created in Keycloak.
#
# Steps performed by the script:
# 1. Logs in to Keycloak and retrieves an access token.
# 2. Creates a new client with the specified CLIENT_ID.
#    - If the client already exists, it skips the creation.
# 3. Retrieves the UUID of the created client.
# 4. Enables client authentication capability with service account roles checked.
# 5. Updates the realm settings to set the access token lifespan to 15 minutes.
# 6. Retrieves the client secret and stores it in a Kubernetes Secret
#    (CLIENT_SECRET_K8S_SECRET). When not running in-cluster, it is printed.
#
# Dependencies:
# - curl: Command-line tool for making HTTP requests.
# - jq: Command-line JSON processor.
#
# Exit codes:
# 0 - Script executed successfully.
# 1 - An error occurred during the execution of the script.


KEYCLOAK_URL="http://$1"
USERNAME="${KEYCLOAK_ADMIN_USER:-$2}"
PASSWORD="${KEYCLOAK_ADMIN_PASSWORD:-$3}"
CLIENT_ID="${KEYCLOAK_CLIENT_ID:-$4}"

CLIENT_SECRET_K8S_SECRET="${CLIENT_SECRET_K8S_SECRET:-keycloak-client-secret}"

if [ -z "$USERNAME" ] || [ -z "$PASSWORD" ] || [ -z "$CLIENT_ID" ]; then
    echo "ERROR: admin user, password and client id must be provided via environment (or positional args for standalone use)"
    exit 1
fi

# Get access token
TOKEN=$(curl -s -X POST "$KEYCLOAK_URL/realms/master/protocol/openid-connect/token" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "username=$USERNAME" \
    -d "password=$PASSWORD" \
    -d 'grant_type=password' \
    -d 'client_id=admin-cli' | jq -r '.access_token')

if [ -z "$TOKEN" ]; then
    echo "Login failed"
    exit 1
else
    echo "Logged in successfully"
fi


# Create new client
CLIENT_RESPONSE=$(curl -s -X POST "$KEYCLOAK_URL/admin/realms/master/clients" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    -d '{
        "clientId": "'$CLIENT_ID'",
        "protocol": "openid-connect",
        "publicClient": false,
        "serviceAccountsEnabled": true
    }')

if echo "$CLIENT_RESPONSE" | grep -q '"errorMessage":"Client '$CLIENT_ID' already exists"'; then
    echo "Client $CLIENT_ID already exists, skipping creation"
else
    if [ -z "$CLIENT_RESPONSE" ]; then
        echo "Client created successfully"
    else
        echo "Failed to create client: $CLIENT_RESPONSE"
        exit 1
    fi
fi

# Get client UUID
CLIENT_UUID=$(curl -s -X GET "$KEYCLOAK_URL/admin/realms/master/clients?clientId=$CLIENT_ID" \
    -H "Authorization: Bearer $TOKEN" | jq -r '.[0].id')

if [ -z "$CLIENT_UUID" ]; then
    echo "Failed to retrieve client UUID"
    exit 1
fi

# Enable Client authentication capability config with Service account roles checked
UPDATE_CLIENT_RESPONSE=$(curl -s -X PUT "$KEYCLOAK_URL/admin/realms/master/clients/$CLIENT_UUID" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    -d '{
        "serviceAccountsEnabled": true
    }')

if [ -z "$UPDATE_CLIENT_RESPONSE" ]; then
    echo "Client authentication capability updated successfully"
else
    echo "Failed to update client authentication capability: $UPDATE_CLIENT_RESPONSE"
    exit 1
fi

# Update the Realm settings for access token lifespan to 15 minutes
UPDATE_REALM_RESPONSE=$(curl -s -X PUT "$KEYCLOAK_URL/admin/realms/master" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    -d '{
        "accessTokenLifespan": 900
    }')

if [ -z "$UPDATE_REALM_RESPONSE" ]; then
    echo "Realm settings for access token lifespan updated successfully to 15 mins"
else
    echo "Failed to update realm settings: $UPDATE_REALM_RESPONSE"
    exit 1
fi

echo "Script executed successfully"

# Get client secret
CLIENT_SECRET=$(curl -s -X GET "$KEYCLOAK_URL/admin/realms/master/clients/$CLIENT_UUID/client-secret" \
    -H "Authorization: Bearer $TOKEN" | jq -r '.value')

if [ -z "$CLIENT_SECRET" ] || [ "$CLIENT_SECRET" = "null" ]; then
    echo "Failed to retrieve client secret"
    exit 1
fi

SA_DIR="/var/run/secrets/kubernetes.io/serviceaccount"
if [ -f "$SA_DIR/token" ] && [ -n "$KUBERNETES_SERVICE_HOST" ]; then
    K8S_TOKEN=$(cat "$SA_DIR/token")
    K8S_NAMESPACE=$(cat "$SA_DIR/namespace")
    K8S_CACERT="$SA_DIR/ca.crt"
    K8S_API="https://$KUBERNETES_SERVICE_HOST:${KUBERNETES_SERVICE_PORT_HTTPS:-443}"
    SECRET_B64=$(printf '%s' "$CLIENT_SECRET" | base64 | tr -d '\n')

    SECRET_PAYLOAD=$(jq -nc \
        --arg name "$CLIENT_SECRET_K8S_SECRET" \
        --arg ns "$K8S_NAMESPACE" \
        --arg data "$SECRET_B64" \
        '{apiVersion:"v1",kind:"Secret",metadata:{name:$name,namespace:$ns},type:"Opaque",data:{"client-secret":$data}}')

    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --cacert "$K8S_CACERT" \
        -X GET "$K8S_API/api/v1/namespaces/$K8S_NAMESPACE/secrets/$CLIENT_SECRET_K8S_SECRET" \
        -H "Authorization: Bearer $K8S_TOKEN")

    if [ "$HTTP_CODE" = "200" ]; then
        RESP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --cacert "$K8S_CACERT" \
            -X PUT "$K8S_API/api/v1/namespaces/$K8S_NAMESPACE/secrets/$CLIENT_SECRET_K8S_SECRET" \
            -H "Authorization: Bearer $K8S_TOKEN" \
            -H "Content-Type: application/json" \
            -d "$SECRET_PAYLOAD")
    else
        RESP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --cacert "$K8S_CACERT" \
            -X POST "$K8S_API/api/v1/namespaces/$K8S_NAMESPACE/secrets" \
            -H "Authorization: Bearer $K8S_TOKEN" \
            -H "Content-Type: application/json" \
            -d "$SECRET_PAYLOAD")
    fi

    if [ "$RESP_CODE" = "200" ] || [ "$RESP_CODE" = "201" ]; then
        echo "Client secret stored in Kubernetes Secret '$CLIENT_SECRET_K8S_SECRET' (namespace: $K8S_NAMESPACE)"
    else
        echo "ERROR: failed to store client secret in Kubernetes Secret (HTTP $RESP_CODE)"
        exit 1
    fi
else
    echo "Client secret: $CLIENT_SECRET"
fi
