#!/bin/bash
# Script to verify Ubuntu installation completion
#
# Environment variables:
#   IDRAC_IP or IDRAC_HOST - iDRAC IP address or hostname (required)
#   IDRAC_USER or IDRAC_USERNAME - iDRAC username (required)
#   IDRAC_PASS or IDRAC_PASSWORD - iDRAC password (required)

set -e

# Read from environment variables with fallback options
IDRAC_IP="${IDRAC_IP:-${IDRAC_HOST}}"
IDRAC_USER="${IDRAC_USER:-${IDRAC_USERNAME}}"
IDRAC_PASS="${IDRAC_PASS:-${IDRAC_PASSWORD}}"

# Validate required environment variables
if [ -z "$IDRAC_IP" ]; then
    echo "❌ Error: IDRAC_IP or IDRAC_HOST environment variable is required"
    exit 1
fi

if [ -z "$IDRAC_USER" ]; then
    echo "❌ Error: IDRAC_USER or IDRAC_USERNAME environment variable is required"
    exit 1
fi

if [ -z "$IDRAC_PASS" ]; then
    echo "❌ Error: IDRAC_PASS or IDRAC_PASSWORD environment variable is required"
    exit 1
fi

EXPECTED_HOSTNAME="ubuntu-server"  # From terraform.tfvars

echo "=========================================="
echo "Ubuntu Installation Verification"
echo "=========================================="
echo ""

# Check hostname change
echo "1. Checking hostname (should change from MINWINPC)..."
HOSTNAME=$(curl -sk -u "${IDRAC_USER}:${IDRAC_PASS}" \
  "https://${IDRAC_IP}/redfish/v1/Systems/System.Embedded.1" \
  2>/dev/null | python3 -c "import sys, json; print(json.load(sys.stdin).get('HostName', 'N/A'))" 2>/dev/null || echo "N/A")

if [ "$HOSTNAME" != "MINWINPC" ] && [ "$HOSTNAME" != "N/A" ]; then
    echo "   ✅ Hostname changed to: $HOSTNAME"
    echo "   → Ubuntu installation appears successful!"
else
    echo "   ⚠️  Hostname still: $HOSTNAME (may still be installing)"
fi

echo ""

# Check boot override status (should revert after installation)
echo "2. Checking boot configuration..."
BOOT_OVERRIDE=$(curl -sk -u "${IDRAC_USER}:${IDRAC_PASS}" \
  "https://${IDRAC_IP}/redfish/v1/Systems/System.Embedded.1/Boot" \
  2>/dev/null | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('BootSourceOverrideEnabled', 'N/A'))" 2>/dev/null || echo "N/A")

if [ "$BOOT_OVERRIDE" = "Disabled" ]; then
    echo "   ✅ Boot override disabled (installation completed, system booted from installed OS)"
elif [ "$BOOT_OVERRIDE" = "Once" ]; then
    echo "   ⚠️  Boot override still active (installation may still be in progress)"
else
    echo "   ℹ️  Boot override status: $BOOT_OVERRIDE"
fi

echo ""

# Check power state
echo "3. Checking system power state..."
POWER_STATE=$(curl -sk -u "${IDRAC_USER}:${IDRAC_PASS}" \
  "https://${IDRAC_IP}/redfish/v1/Systems/System.Embedded.1" \
  2>/dev/null | python3 -c "import sys, json; print(json.load(sys.stdin).get('PowerState', 'N/A'))" 2>/dev/null || echo "N/A")

echo "   Power State: $POWER_STATE"
if [ "$POWER_STATE" = "On" ]; then
    echo "   ✅ System is powered on"
else
    echo "   ⚠️  System power state: $POWER_STATE"
fi

echo ""

# Try to detect Ubuntu via network (if SSH is enabled)
echo "4. Network connectivity check..."
echo "   Note: Try to SSH to the server if you know the IP:"
echo "   ssh user@<server-ip>"
echo "   Password: Linux123!"

echo ""
echo "=========================================="
echo "Recommended: Use iDRAC Virtual Console"
echo "=========================================="
echo "1. Access: https://${IDRAC_IP}"
echo "2. Login with: ${IDRAC_USER} / ${IDRAC_PASS}"
echo "3. Open Virtual Console"
echo "4. You should see Ubuntu Desktop login screen"
echo ""
