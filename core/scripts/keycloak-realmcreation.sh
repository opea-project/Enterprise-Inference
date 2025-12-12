#!/bin/bash

# Copyright (C) 2024-2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
# Permission is granted for recipient to internally use and modify this software for purposes of benchmarking and testing on Intel architectures. 
# This software is provided "AS IS" possibly with faults, bugs or errors; it is not intended for production use, and recipient uses this design at their own risk with no liability to Intel.
# Intel disclaims all warranties, express or implied, including warranties of merchantability, fitness for a particular purpose, and non-infringement. 
# Recipient agrees that any feedback it provides to Intel about this software is licensed to Intel for any purpose worldwide. No permission is granted to use Intel’s trademarks.
# The above copyright notice and this permission notice shall be included in all copies or substantial portions of the code.



# This script automates the creation and configuration of a Keycloak client.
# 
# Usage:
# ./keycloak-realmcreation.sh <KEYCLOAK_URL> <USERNAME> <PASSWORD> <CLIENT_ID>
#
# Arguments:
#   KEYCLOAK_URL - The base URL of the Keycloak server.
#   USERNAME     - The username for Keycloak admin login.
#   PASSWORD     - The password for Keycloak admin login.
#   CLIENT_ID    - The client ID to be created in Keycloak.
#
# Steps performed by the script:
# 1. Logs in to Keycloak and retrieves an access token.
# 2. Creates a new client with the specified CLIENT_ID.
#    - If the client already exists, it skips the creation.
# 3. Retrieves the UUID of the created client.
# 4. Enables client authentication capability with service account roles checked.
# 5. Updates the realm settings to set the access token lifespan to 15 minutes.
# 6. Retrieves and displays the client secret.
#
# Dependencies:
# - curl: Command-line tool for making HTTP requests.
# - jq: Command-line JSON processor.
#
# Exit codes:
# 0 - Script executed successfully.
# 1 - An error occurred during the execution of the script.


KEYCLOAK_URL="http://$1"
USERNAME=$2
PASSWORD=$3
CLIENT_ID=$4

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

if [ -z "$CLIENT_SECRET" ]; then
    echo "Failed to retrieve client secret"
    exit 1
else
    echo "Client secret: $CLIENT_SECRET"
fi
