#!/usr/bin/env bash
set -euo pipefail

ISO_URL="https://releases.ubuntu.com/jammy/ubuntu-22.04.5-live-server-amd64.iso"
ISO_NAME="ubuntu-22.04.5-live-server-amd64.iso"
ISO_PATH=""
OUT_ISO="ubuntu-22.04.5-autoinstall.iso"
VOLID="Ubuntu-Server-22.04.5-AI"

HOSTNAME=""
USERNAME=""
PASSWORD_HASH='$6$Sl0xydNgA3rBk1Uo$Pj7oVVI7smkdBh20V8EyLivWpKDHFueUhvrfwxundGp/DQrAuTHjIxnrCZIMVJ1zcTIJ7VgIWKu0mUZmiRsqv0'
SSH_PUBLIC_KEY=""
TIMEZONE="America/Chicago"
LOCALE="en_US.UTF-8"
KBD_LAYOUT="us"
KBD_VARIANT=""
STORAGE_LAYOUT="direct"
INSTANCE_ID="ubuntu-server-001"
PACKAGES=""

usage() {
  cat <<EOT
Usage: $0 [options]
  --hostname VALUE                 (required)
  --username VALUE                 (required)
  --password-hash VALUE            (required)
  --ssh-key VALUE                  (optional)
  --timezone VALUE                 (default: $TIMEZONE)
  --locale VALUE                   (default: $LOCALE)
  --kbd-layout VALUE               (default: $KBD_LAYOUT)
  --kbd-variant VALUE              (default: "$KBD_VARIANT")
  --storage-layout VALUE           (default: $STORAGE_LAYOUT)
  --instance-id VALUE              (default: $INSTANCE_ID)
  --packages CSV                   (comma-separated, optional)
  --iso PATH                       (use a local ISO file)
  --iso-url URL                    (download ISO if --iso not provided)
  --iso-name NAME                  (filename to save ISO URL as)
  --out-iso PATH                   (default: $OUT_ISO)
  --volid VALUE                    (default: $VOLID, max 32 chars)
EOT
}

check_cmd() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "Missing required command: $cmd"
    exit 1
  fi
}

for arg in "$@"; do
  case "$arg" in
    --hostname=*) HOSTNAME="${arg#*=}" ;;
    --username=*) USERNAME="${arg#*=}" ;;
    --password-hash=*) PASSWORD_HASH="${arg#*=}" ;;
    --ssh-key=*) SSH_PUBLIC_KEY="${arg#*=}" ;;
    --timezone=*) TIMEZONE="${arg#*=}" ;;
    --locale=*) LOCALE="${arg#*=}" ;;
    --kbd-layout=*) KBD_LAYOUT="${arg#*=}" ;;
    --kbd-variant=*) KBD_VARIANT="${arg#*=}" ;;
    --storage-layout=*) STORAGE_LAYOUT="${arg#*=}" ;;
    --instance-id=*) INSTANCE_ID="${arg#*=}" ;;
    --packages=*) PACKAGES="${arg#*=}" ;;
    --iso=*) ISO_PATH="${arg#*=}" ;;
    --iso-url=*) ISO_URL="${arg#*=}" ;;
    --iso-name=*) ISO_NAME="${arg#*=}" ;;
    --out-iso=*) OUT_ISO="${arg#*=}" ;;
    --volid=*) VOLID="${arg#*=}" ;;
    --help|-h) usage; exit 0 ;;
    *) echo "Unknown option: $arg"; usage; exit 1 ;;
  esac
done

if [[ -z "$HOSTNAME" || -z "$USERNAME" || -z "$PASSWORD_HASH" ]]; then
  echo "Missing required: --hostname, --username, --password-hash"
  usage
  exit 1
fi

if (( ${#VOLID} > 32 )); then
  echo "VOLID too long (max 32 chars): $VOLID"
  exit 1
fi

check_cmd curl
check_cmd rsync
check_cmd xorriso

if [[ "$OSTYPE" != "darwin"* ]]; then
  check_cmd mount
  check_cmd umount
fi

WORKDIR="$(mktemp -d)"
MNTDIR="$WORKDIR/mnt"
EXTRACTDIR="$WORKDIR/extract"
USERDATA_FILE="$WORKDIR/user-data"
METADATA_FILE="$WORKDIR/meta-data"

cleanup() {
  if mount | grep -q "$MNTDIR"; then
    if [[ "$OSTYPE" == "darwin"* ]]; then
      hdiutil detach "$MNTDIR" || true
    else
      sudo umount "$MNTDIR" || true
    fi
  fi
  if [[ -d "$EXTRACTDIR" ]]; then
    chmod -R u+rwX "$EXTRACTDIR" >/dev/null 2>&1 || true
  fi
  rm -rf "$WORKDIR"
}
trap cleanup EXIT

if [[ -n "$ISO_PATH" ]]; then
  if [[ ! -f "$ISO_PATH" ]]; then
    echo "ISO not found: $ISO_PATH"
    exit 1
  fi
else
  if [[ -z "$ISO_NAME" ]]; then
    ISO_NAME="$(basename "$ISO_URL")"
  fi
  ISO_PATH="$ISO_NAME"
  if [[ ! -f "$ISO_PATH" ]]; then
    echo "Downloading ISO..."
    curl -L -o "$ISO_PATH" "$ISO_URL"
  fi
fi

mkdir -p "$MNTDIR" "$EXTRACTDIR"

echo "Generating user-data and meta-data..."
{
  echo "#cloud-config"
  echo "autoinstall:"
  echo "  version: 1"
  echo "  identity:"
  echo "    hostname: $HOSTNAME"
  echo "    username: $USERNAME"
  echo "    password: $PASSWORD_HASH"
  echo "  locale: $LOCALE"
  echo "  keyboard:"
  echo "    layout: $KBD_LAYOUT"
  if [[ -n "$KBD_VARIANT" ]]; then
    echo "    variant: $KBD_VARIANT"
  fi
  echo "  timezone: $TIMEZONE"
  echo "  ssh:"
  echo "    install-server: true"
  if [[ -n "$SSH_PUBLIC_KEY" ]]; then
    echo "    authorized-keys:"
    echo "      - $SSH_PUBLIC_KEY"
  fi
  echo "  storage:"
  echo "    layout:"
  echo "      name: $STORAGE_LAYOUT"
  if [[ -n "$PACKAGES" ]]; then
    echo "  packages:"
    IFS=',' read -r -a PKGS <<< "$PACKAGES"
    for p in "${PKGS[@]}"; do
      echo "    - $p"
    done
  fi
  echo "  user-data:"
  echo "    disable_root: true"
  echo "  late-commands:"
  echo "    - curtin in-target --target=/target -- echo \"Autoinstall complete\" > /target/var/log/autoinstall_complete"
} > "$USERDATA_FILE"

{
  echo "instance-id: $INSTANCE_ID"
  echo "local-hostname: $HOSTNAME"
} > "$METADATA_FILE"

if [[ "$OSTYPE" == "darwin"* ]]; then
  echo "Extracting ISO with xorriso..."
  xorriso -osirrox on -indev "$ISO_PATH" -extract / "$EXTRACTDIR"
  chmod -R u+rwX "$EXTRACTDIR" >/dev/null 2>&1 || true
else
  echo "Mounting ISO..."
  sudo mount -o loop "$ISO_PATH" "$MNTDIR"
  echo "Copying ISO contents..."
  rsync -a "$MNTDIR"/ "$EXTRACTDIR"/
  echo "Unmounting ISO..."
  sudo umount "$MNTDIR"
fi

echo "Adding user-data and meta-data..."
cp "$USERDATA_FILE" "$EXTRACTDIR"/user-data
cp "$METADATA_FILE" "$EXTRACTDIR"/meta-data

echo "Patching boot configs..."
for f in \
  "$EXTRACTDIR/boot/grub/grub.cfg" \
  "$EXTRACTDIR/boot/grub/loopback.cfg" \
  "$EXTRACTDIR/isolinux/txt.cfg"
do
  if [[ -f "$f" ]]; then
    sed -i.bak 's/---/autoinstall ds=nocloud\\;s=\/cdrom\/ ---/g' "$f"
  fi
done

echo "Rebuilding ISO..."
BOOT_ARGS_RAW="$(
  xorriso -indev "$ISO_PATH" -report_el_torito as_mkisofs \
    | tail -n +2 \
    | grep -v "^-V " \
    | grep -v "^--modification-date="
)"
BOOT_ARGS="$(echo "$BOOT_ARGS_RAW" | tr '\n' ' ')"
eval "xorriso -as mkisofs $BOOT_ARGS -V \"$VOLID\" -o \"$OUT_ISO\" -J -l -r \"$EXTRACTDIR\""

echo "Done: $OUT_ISO"
