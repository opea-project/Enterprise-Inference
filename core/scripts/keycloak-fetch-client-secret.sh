#!/bin/bash

# Copyright (C) 2024-2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
# Permission is granted for recipient to internally use and modify this software for purposes of benchmarking and testing on Intel architectures. 
# This software is provided "AS IS" possibly with faults, bugs or errors; it is not intended for production use, and recipient uses this design at their own risk with no liability to Intel.
# Intel disclaims all warranties, express or implied, including warranties of merchantability, fitness for a particular purpose, and non-infringement. 
# Recipient agrees that any feedback it provides to Intel about this software is licensed to Intel for any purpose worldwide. No permission is granted to use Intel’s trademarks.
# The above copyright notice and this permission notice shall be included in all copies or substantial portions of the code.



# This script automates the fetching of Keycloak client secret.
# 
# Usage:
# bash keycloak-fetch-client-secret.sh <KEYCLOAK_URL> <USERNAME> <PASSWORD> <CLIENT_ID>
#
# Arguments:
#   KEYCLOAK_URL - The base URL of the Keycloak server.
#   USERNAME     - The username for Keycloak admin login.
#   PASSWORD     - The password for Keycloak admin login.
#   CLIENT_ID    - The client ID to be created in Keycloak.
#
# Steps performed by the script:
# 1. Logs in to Keycloak and retrieves an access token.
# 2. Retrieves the UUID of the created client.
# 3. Retrieves and displays the client secret.
#
# Dependencies:
# - curl: Command-line tool for making HTTP requests.
# - jq: Command-line JSON processor.
#
# Exit codes:
# 0 - Script executed successfully.
# 1 - An error occurred during the execution of the script.


KEYCLOAK_URL="https://$1"
USERNAME=$2
PASSWORD=$3
CLIENT_ID=$4

# Get access token
TOKEN=$(curl -s -k -X POST "$KEYCLOAK_URL/realms/master/protocol/openid-connect/token" \
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

# Get client UUID
CLIENT_UUID=$(curl -s -k -X GET "$KEYCLOAK_URL/admin/realms/master/clients?clientId=$CLIENT_ID" \
    -H "Authorization: Bearer $TOKEN" | jq -r '.[0].id')

if [ -z "$CLIENT_UUID" ]; then
    echo "Failed to retrieve client UUID"
    exit 1
fi


# Get client secret
CLIENT_SECRET=$(curl -s -k -X GET "$KEYCLOAK_URL/admin/realms/master/clients/$CLIENT_UUID/client-secret" \
    -H "Authorization: Bearer $TOKEN" | jq -r '.value')

if [ -z "$CLIENT_SECRET" ]; then
    echo "Failed to retrieve client secret"
    exit 1
else
    echo "Client secret: $CLIENT_SECRET"
fi
