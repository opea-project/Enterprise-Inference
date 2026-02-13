# Ubuntu Autoinstall ISO Builder

This provides a single script (`custom-iso.sh`) that builds an Ubuntu Server autoinstall ISO. The script:

- Generates `user-data` and `meta-data` on the fly from CLI options.
- Accepts a local ISO file path or downloads an ISO from a URL.
- Preserves boot settings from the input ISO so the output remains bootable.

## Prerequisites

### Linux
- `bash`
- `curl`
- `rsync`
- `xorriso`
- `sudo`
- `mount`/`umount`

Example (Ubuntu/Debian):

```bash
sudo apt-get update
sudo apt-get install -y curl rsync xorriso
```

### macOS
- `bash` (default)
- `curl` (default)
- `rsync` (Homebrew recommended)
- `xorriso` (Homebrew)

Install on macOS:

```bash
brew install xorriso rsync
```

## Usage

The script requires `--hostname`, `--username`, and `--password-hash`. All other values have defaults.

Basic example using a local ISO:

```bash
./custom-iso.sh \
  --hostname=ubuntu-server-001 \
  --username=user \
  --iso=./ubuntu-22.04.5-live-server-amd64.iso
```

Full example with all options:

```bash
./custom-iso.sh \
  --hostname=ubuntu-server-001 \
  --username=user \
  --password-hash='$6$Sl0xydNgA3rBk1Uo$Pj7oVVI7smkdBh20V8EyLivWpKDHFueUhvrfwxundGp/DQrAuTHjIxnrCZIMVJ1zcTIJ7VgIWKu0mUZmiRsqv0' \
  --ssh-key='' \
  --timezone=America/Chicago \
  --locale=en_US.UTF-8 \
  --kbd-layout=us \
  --kbd-variant='' \
  --storage-layout=direct \
  --instance-id=ubuntu-server-001 \
  --packages='' \
  --iso=./ubuntu-22.04.5-live-server-amd64.iso \
  --iso-url=https://releases.ubuntu.com/jammy/ubuntu-22.04.5-live-server-amd64.iso \
  --iso-name=ubuntu-22.04.5-live-server-amd64.iso \
  --out-iso=ubuntu-22.04.5-autoinstall.iso \
  --volid=Ubuntu-Server-22.04.5-AI
```

Notes:
- If `--iso` is provided, `--iso-url` and `--iso-name` are ignored.
- If `--ssh-key` is empty, no SSH key is embedded.
- `--packages` is a comma-separated list (e.g., `--packages=openssh-server,curl`).
- `--volid` must be 32 characters or fewer.

## Options and Defaults

| Option | Required | Default | Description |
|---|---|---|---|
| `--hostname` | Yes | (none) | Hostname for the installed system. |
| `--username` | Yes | (none) | Primary user name. |
| `--password-hash` | Yes | (none) | SHA-512 password hash for the user. |
| `--ssh-key` | No | `""` | SSH public key (optional). |
| `--timezone` | No | `America/Chicago` | System timezone. |
| `--locale` | No | `en_US.UTF-8` | Locale. |
| `--kbd-layout` | No | `us` | Keyboard layout. |
| `--kbd-variant` | No | `""` | Keyboard variant (optional). |
| `--storage-layout` | No | `direct` | Storage layout. Use `direct` for whole disk or `lvm`. |
| `--instance-id` | No | `ubuntu-server-001` | Cloud-init instance ID. |
| `--packages` | No | `""` | Comma-separated package list. |
| `--iso` | No | `""` | Local ISO file path. |
| `--iso-url` | No | Ubuntu 22.04.5 URL | Download ISO from URL. |
| `--iso-name` | No | `ubuntu-22.04.5-live-server-amd64.iso` | Filename for downloaded ISO. |
| `--out-iso` | No | `ubuntu-22.04.5-autoinstall.iso` | Output ISO filename. |
| `--volid` | No | `Ubuntu-Server-22.04.5-AI` | ISO volume ID (max 32 chars). |

## Output

The script writes the rebuilt ISO to the path specified by `--out-iso` (default `ubuntu-22.04.5-autoinstall.iso`).

## UTM Test Notes (macOS)

If testing in UTM and you see a `Shell>` prompt:
- On Apple Silicon, you must use **Emulate → x86_64** for this amd64 ISO.
- In the UEFI shell, type `exit`, then select the CD/DVD boot entry.

If the installer logs repeatedly mention networking updates, verify UTM’s network mode is set to **Shared** or **Bridged**.