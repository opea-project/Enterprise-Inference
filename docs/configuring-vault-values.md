# Configuring Vault Values

This document explains how to configure and manage encrypted vault values for deployment.

## Overview

The vault file contains sensitive configuration values like passwords, API keys, and secrets that should not be stored in plain text. This file is encrypted using Ansible Vault and is located at:

```
inventory/metadata/vault.yml
```

## Getting Started

### 1. Decrypt the Vault File

To edit the vault file, you first need to decrypt it:

```bash
ansible-vault decrypt inventory/metadata/vault.yml
```

**Default Password:** `place-holder-123`

### 2. Update Your Values

Once decrypted, edit the `vault.yml` file with your actual values:

```yaml
# Example values (replace with your actual secrets)
litellm_master_key: "your-actual-master-key"
litellm_salt_key: "your-actual-salt-key"
redis_password: "your-redis-password"
postgresql_password: "your-db-password"
# ... add other secrets as needed
```

### 3. Encrypt the Vault File

After making your changes, encrypt the file again:

```bash
ansible-vault encrypt inventory/metadata/vault.yml
```

**Important:** Always encrypt the vault file before committing to version control.

## Changing the Vault Password

You can customize the vault password by updating the configuration in:

```
core/inventory/inference-config.cfg
```

Look for the key:
```
vault-pass-code=your-new-password
```

After changing the password, you'll need to rekey your existing vault file:

```bash
ansible-vault rekey inventory/metadata/vault.yml
```

## Best Practices

1. **Use strong, unique passwords** for your vault
2. **Backup your vault password** securely
3. **Use different vault files** for different environments (dev, staging, prod)

## Security Notes
- The vault file should have restricted permissions (600 or 640)

## Example Workflow

```bash
# 1. Decrypt the vault
ansible-vault decrypt inventory/metadata/vault.yml

# 2. Edit the file
nano inventory/metadata/vault.yml

# 3. Encrypt the file
ansible-vault encrypt inventory/metadata/vault.yml
```
