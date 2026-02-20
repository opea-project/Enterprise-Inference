#!/bin/bash
# Script to mount/unmount Ubuntu ISO via iDRAC Redfish API
# Usage:
#   ./mount-iso.sh          - Mount the ISO
#   ./mount-iso.sh --unmount - Unmount the ISO
#   ./mount-iso.sh -u        - Unmount the ISO
#
# Environment variables:
#   IDRAC_IP or IDRAC_HOST - iDRAC IP address or hostname (required)
#   IDRAC_USER or IDRAC_USERNAME - iDRAC username (required)
#   IDRAC_PASS or IDRAC_PASSWORD - iDRAC password (required)

set -e

# Parse command line arguments
UNMOUNT=false
if [ "$1" = "--unmount" ] || [ "$1" = "-u" ]; then
    UNMOUNT=true
fi

# Read from environment variables with fallback options
IDRAC_IP="${IDRAC_IP:-${IDRAC_HOST}}"
IDRAC_USER="${IDRAC_USER:-${IDRAC_USERNAME}}"
IDRAC_PASS="${IDRAC_PASS:-${IDRAC_PASSWORD}}"
DEFAULT_ISO_URL="https://releases.ubuntu.com/22.04/ubuntu-22.04.5-live-server-amd64.iso"
ISO_URL="${ISO_URL:-$DEFAULT_ISO_URL}"

# Validate required environment variables
if [ -z "$IDRAC_IP" ]; then
    echo "❌ Error: IDRAC_IP or IDRAC_HOST environment variable is required"
    echo "   Example: export IDRAC_IP=100.67.153.16"
    exit 1
fi

if [ -z "$IDRAC_USER" ]; then
    echo "❌ Error: IDRAC_USER or IDRAC_USERNAME environment variable is required"
    echo "   Example: export IDRAC_USER=root"
    exit 1
fi

if [ -z "$IDRAC_PASS" ]; then
    echo "❌ Error: IDRAC_PASS or IDRAC_PASSWORD environment variable is required"
    echo "   Example: export IDRAC_PASS=calvin"
    exit 1
fi


#ISO_URL="https://releases.ubuntu.com/22.04/ubuntu-22.04.5-live-server-amd64.iso"
SYSTEM_ID="System.Embedded.1"
VIRTUAL_MEDIA_SLOT="1"

if [ "$UNMOUNT" = true ]; then
    echo "=========================================="
    echo "Unmounting Virtual Media via iDRAC Redfish API"
    echo "=========================================="
    echo ""
    
    # Check current status
    echo "Checking current virtual media status..."
    CURRENT_IMAGE=$(curl -sk --max-time 10 --connect-timeout 5 -u "${IDRAC_USER}:${IDRAC_PASS}" \
      "https://${IDRAC_IP}/redfish/v1/Systems/${SYSTEM_ID}/VirtualMedia/${VIRTUAL_MEDIA_SLOT}" \
      2>/dev/null | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('Image', 'None'))" 2>/dev/null || echo "None")
    
    if [ "$CURRENT_IMAGE" = "None" ] || [ "$CURRENT_IMAGE" = "null" ] || [ -z "$CURRENT_IMAGE" ]; then
        echo "ℹ️  No media is currently mounted"
        exit 0
    fi
    
    echo "Current mounted image: $CURRENT_IMAGE"
    echo ""
    echo "Unmounting media..."
    
    RESPONSE=$(curl -sk --max-time 10 --connect-timeout 5 -w "\n%{http_code}" -u "${IDRAC_USER}:${IDRAC_PASS}" \
      -X POST \
      "https://${IDRAC_IP}/redfish/v1/Systems/${SYSTEM_ID}/VirtualMedia/${VIRTUAL_MEDIA_SLOT}/Actions/VirtualMedia.EjectMedia" \
      -H "Content-Type: application/json" \
      -d '{}' 2>&1)
    
    HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
    BODY=$(echo "$RESPONSE" | sed '$d')
    
    if [[ "$HTTP_CODE" =~ ^(200|202|204)$ ]]; then
        echo "✅ Media unmounted successfully!"
        echo ""
        echo "Verifying unmount..."
        sleep 2
        
        VERIFY_IMAGE=$(curl -sk --max-time 10 --connect-timeout 5 -u "${IDRAC_USER}:${IDRAC_PASS}" \
          "https://${IDRAC_IP}/redfish/v1/Systems/${SYSTEM_ID}/VirtualMedia/${VIRTUAL_MEDIA_SLOT}" \
          2>/dev/null | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('Image', 'None'))" 2>/dev/null || echo "None")
        
        if [ "$VERIFY_IMAGE" = "None" ] || [ "$VERIFY_IMAGE" = "null" ]; then
            echo "   ✅ Confirmed: No media mounted"
            exit 0
        else
            echo "   ⚠️  Media may still be mounted: $VERIFY_IMAGE"
            exit 1
        fi
    else
        echo "❌ Failed to unmount media. HTTP Code: $HTTP_CODE"
        echo "Response: $BODY"
        exit 1
    fi
fi

echo "=========================================="
echo "Mounting Ubuntu ISO via iDRAC Redfish API"
echo "=========================================="
echo ""

# Check if ISO is already mounted
echo "Checking current virtual media status..."
CURRENT_IMAGE=$(curl -sk --max-time 10 --connect-timeout 5 -u "${IDRAC_USER}:${IDRAC_PASS}" \
  "https://${IDRAC_IP}/redfish/v1/Systems/${SYSTEM_ID}/VirtualMedia/${VIRTUAL_MEDIA_SLOT}" \
  2>/dev/null | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('Image', 'None'))" 2>/dev/null || echo "None")

if [ "$CURRENT_IMAGE" = "$ISO_URL" ]; then
    echo "✅ ISO is already mounted: $ISO_URL"
    echo "   ConnectedVia: $(curl -sk -u "${IDRAC_USER}:${IDRAC_PASS}" "https://${IDRAC_IP}/redfish/v1/Systems/${SYSTEM_ID}/VirtualMedia/${VIRTUAL_MEDIA_SLOT}" 2>/dev/null | python3 -c "import sys, json; print(json.load(sys.stdin).get('ConnectedVia', 'N/A'))" 2>/dev/null || echo "N/A")"
    echo ""
    echo "Skipping mount - ISO already in place."
    exit 0
fi

# Eject existing media if any
if [ "$CURRENT_IMAGE" != "None" ] && [ "$CURRENT_IMAGE" != "null" ]; then
    echo "⚠️  Ejecting existing media: $CURRENT_IMAGE"
    curl -sk --max-time 10 --connect-timeout 5 -u "${IDRAC_USER}:${IDRAC_PASS}" \
      -X POST \
      "https://${IDRAC_IP}/redfish/v1/Systems/${SYSTEM_ID}/VirtualMedia/${VIRTUAL_MEDIA_SLOT}/Actions/VirtualMedia.EjectMedia" \
      -H "Content-Type: application/json" \
      -d '{}' \
      > /dev/null 2>&1 || echo "   (Eject may have failed, continuing anyway...)"
    sleep 2
fi

if [[ "$ISO_URL" =~ ^https:// ]]; then
    TRANSFER_PROTOCOL="HTTPS"
elif [[ "$ISO_URL" =~ ^http:// ]]; then
    TRANSFER_PROTOCOL="HTTP"
else
    echo "❌ Unsupported ISO URL scheme: $ISO_URL"
    exit 1
fi

# Mount the ISO
echo "Mounting ISO: $ISO_URL"
echo ""

RESPONSE=$(curl -sk --max-time 30 --connect-timeout 10 -w "\n%{http_code}" -u "${IDRAC_USER}:${IDRAC_PASS}" \
  -X POST \
  "https://${IDRAC_IP}/redfish/v1/Systems/${SYSTEM_ID}/VirtualMedia/${VIRTUAL_MEDIA_SLOT}/Actions/VirtualMedia.InsertMedia" \
  -H "Content-Type: application/json" \
  -d "{
    \"Image\": \"${ISO_URL}\",
    \"TransferMethod\": \"Stream\",
    \"TransferProtocolType\": \"${TRANSFER_PROTOCOL}\"
  }")

HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | sed '$d')

if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "202" ] || [ "$HTTP_CODE" = "204" ]; then
    echo "✅ ISO mounted successfully!"
    echo ""
    echo "Verifying mount..."
    sleep 3
    
    MOUNTED_IMAGE=$(curl -sk --max-time 10 --connect-timeout 5 -u "${IDRAC_USER}:${IDRAC_PASS}" \
      "https://${IDRAC_IP}/redfish/v1/Systems/${SYSTEM_ID}/VirtualMedia/${VIRTUAL_MEDIA_SLOT}" \
      2>/dev/null | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('Image', 'None'))" 2>/dev/null || echo "None")
    
    CONNECTED_VIA=$(curl -sk --max-time 10 --connect-timeout 5 -u "${IDRAC_USER}:${IDRAC_PASS}" \
      "https://${IDRAC_IP}/redfish/v1/Systems/${SYSTEM_ID}/VirtualMedia/${VIRTUAL_MEDIA_SLOT}" \
      2>/dev/null | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('ConnectedVia', 'N/A'))" 2>/dev/null || echo "N/A")
    
    if [ "$MOUNTED_IMAGE" = "$ISO_URL" ]; then
        echo "   Image: $MOUNTED_IMAGE"
        echo "   ConnectedVia: $CONNECTED_VIA"
        echo ""
        echo "✅ Ready for installation!"
        exit 0
    else
        echo "⚠️  Mount verification failed. Image: $MOUNTED_IMAGE"
        exit 1
    fi
else
    echo "❌ Failed to mount ISO. HTTP Code: $HTTP_CODE"
    echo "Response: $BODY"
    exit 1
fi