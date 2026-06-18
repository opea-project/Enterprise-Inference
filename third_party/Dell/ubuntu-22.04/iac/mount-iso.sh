#!/bin/bash
# Script to mount/unmount Ubuntu ISO via iDRAC Redfish API

set -e

UNMOUNT=false
if [ "$1" = "--unmount" ] || [ "$1" = "-u" ]; then
    UNMOUNT=true
fi

IDRAC_IP="${IDRAC_IP:-${IDRAC_HOST}}"
IDRAC_USER="${IDRAC_USER:-${IDRAC_USERNAME}}"
IDRAC_PASS="${IDRAC_PASS:-${IDRAC_PASSWORD}}"

DEFAULT_ISO_URL="https://releases.ubuntu.com/22.04/ubuntu-22.04.5-live-server-amd64.iso"
ISO_URL="${ISO_URL:-$DEFAULT_ISO_URL}"

SYSTEM_ID="System.Embedded.1"
VIRTUAL_MEDIA_SLOT="1"

MAX_RETRIES=3
SLEEP_INTERVAL=15

# Validate required env vars
if [ -z "$IDRAC_IP" ] || [ -z "$IDRAC_USER" ] || [ -z "$IDRAC_PASS" ]; then
    echo "❌ Missing required environment variables (IDRAC_IP, IDRAC_USER, IDRAC_PASS)"
    exit 1
fi

get_virtual_media_field() {
    local FIELD=$1
    curl -sk --max-time 10 --connect-timeout 5 -u "${IDRAC_USER}:${IDRAC_PASS}" \
      "https://${IDRAC_IP}/redfish/v1/Systems/${SYSTEM_ID}/VirtualMedia/${VIRTUAL_MEDIA_SLOT}" \
      2>/dev/null | python3 -c "import sys, json; print(json.load(sys.stdin).get('${FIELD}', 'None'))" 2>/dev/null || echo "None"
}

verify_mount() {
    echo "Verifying mount..."

    ATTEMPT=1
    while [ $ATTEMPT -le $MAX_RETRIES ]; do
        echo "   Attempt $ATTEMPT of $MAX_RETRIES..."
        sleep $SLEEP_INTERVAL

        IMAGE=$(get_virtual_media_field "Image")
        CONNECTED=$(get_virtual_media_field "ConnectedVia")

        if [ "$IMAGE" = "$ISO_URL" ]; then
            echo "   Image: $IMAGE"
            echo "   ConnectedVia: $CONNECTED"
            echo ""
            echo "✅ Ready for installation!"
            exit 0
        fi

        ATTEMPT=$((ATTEMPT+1))
    done

    echo "❌ Mount verification failed after ${MAX_RETRIES} attempts."
    exit 1
}

verify_unmount() {
    echo "Verifying unmount..."

    ATTEMPT=1
    while [ $ATTEMPT -le $MAX_RETRIES ]; do
        echo "   Attempt $ATTEMPT of $MAX_RETRIES..."
        sleep $SLEEP_INTERVAL

        IMAGE=$(get_virtual_media_field "Image")

        if [ "$IMAGE" = "None" ] || [ "$IMAGE" = "null" ]; then
            echo "   ✅ Confirmed: No media mounted"
            exit 0
        fi

        ATTEMPT=$((ATTEMPT+1))
    done

    echo "❌ Unmount verification failed after ${MAX_RETRIES} attempts."
    exit 1
}

# ---------------- UNMOUNT ----------------

if [ "$UNMOUNT" = true ]; then
    echo "=========================================="
    echo "Unmounting Virtual Media via iDRAC Redfish API"
    echo "=========================================="

    CURRENT_IMAGE=$(get_virtual_media_field "Image")

    if [ "$CURRENT_IMAGE" = "None" ] || [ "$CURRENT_IMAGE" = "null" ]; then
        echo "ℹ️  No media is currently mounted"
        exit 0
    fi

    echo "Current mounted image: $CURRENT_IMAGE"
    echo "Unmounting media..."

    RESPONSE=$(curl -sk -w "\n%{http_code}" -u "${IDRAC_USER}:${IDRAC_PASS}" \
      -X POST \
      "https://${IDRAC_IP}/redfish/v1/Systems/${SYSTEM_ID}/VirtualMedia/${VIRTUAL_MEDIA_SLOT}/Actions/VirtualMedia.EjectMedia" \
      -H "Content-Type: application/json" \
      -d '{}' 2>&1)

    HTTP_CODE=$(echo "$RESPONSE" | tail -n1)

    if [[ "$HTTP_CODE" =~ ^(200|202|204)$ ]]; then
        echo "✅ Media unmounted successfully!"
        verify_unmount
    else
        echo "❌ Failed to unmount media. HTTP Code: $HTTP_CODE"
        exit 1
    fi
fi

# ---------------- MOUNT ----------------

echo "=========================================="
echo "Mounting Ubuntu ISO via iDRAC Redfish API"
echo "=========================================="

CURRENT_IMAGE=$(get_virtual_media_field "Image")

if [ "$CURRENT_IMAGE" = "$ISO_URL" ]; then
    echo "✅ ISO already mounted: $ISO_URL"
    exit 0
fi

if [ "$CURRENT_IMAGE" != "None" ] && [ "$CURRENT_IMAGE" != "null" ]; then
    echo "⚠️  Ejecting existing media: $CURRENT_IMAGE"
    curl -sk -u "${IDRAC_USER}:${IDRAC_PASS}" \
      -X POST \
      "https://${IDRAC_IP}/redfish/v1/Systems/${SYSTEM_ID}/VirtualMedia/${VIRTUAL_MEDIA_SLOT}/Actions/VirtualMedia.EjectMedia" \
      -H "Content-Type: application/json" \
      -d '{}' > /dev/null 2>&1
    sleep 2
fi

if [[ "$ISO_URL" =~ ^https:// ]]; then
    TRANSFER_PROTOCOL="HTTPS"
elif [[ "$ISO_URL" =~ ^http:// ]]; then
    TRANSFER_PROTOCOL="HTTP"
else
    echo "❌ Unsupported ISO URL scheme"
    exit 1
fi

echo "Mounting ISO: $ISO_URL"

RESPONSE=$(curl -sk -w "\n%{http_code}" -u "${IDRAC_USER}:${IDRAC_PASS}" \
  -X POST \
  "https://${IDRAC_IP}/redfish/v1/Systems/${SYSTEM_ID}/VirtualMedia/${VIRTUAL_MEDIA_SLOT}/Actions/VirtualMedia.InsertMedia" \
  -H "Content-Type: application/json" \
  -d "{
    \"Image\": \"${ISO_URL}\",
    \"TransferMethod\": \"Stream\",
    \"TransferProtocolType\": \"${TRANSFER_PROTOCOL}\"
  }")

HTTP_CODE=$(echo "$RESPONSE" | tail -n1)

if [[ "$HTTP_CODE" =~ ^(200|202|204)$ ]]; then
    echo "✅ ISO mount request accepted!"
    verify_mount
else
    echo "❌ Failed to mount ISO. HTTP Code: $HTTP_CODE"
    exit 1
fi