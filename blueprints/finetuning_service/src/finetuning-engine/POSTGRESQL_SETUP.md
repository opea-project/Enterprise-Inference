# PostgreSQL Setup Guide

**Simplified Database Setup for Fine-tuning Engine**

## Overview

The Fine-tuning Engine uses PostgreSQL to store job metadata, training progress, and system metrics. Docker Compose automatically handles database initialization - no manual setup required!

---

## Prerequisites

- Docker and Docker Compose installed
- `.env` file configured with database credentials

---

## Quick Setup (3 Steps)

### 1. Configure Database Credentials in .env

Edit your `.env` file with your desired credentials:

```bash
# Database Configuration
POSTGRES_USER="finetune"
POSTGRES_PASSWORD="your_secure_password_here"
POSTGRES_DB="finetune_db"
DATABASE_URL="postgresql+asyncpg://finetune:your_secure_password_here@postgres:5432/finetune_db"
```

> **Important:** Ensure the username and password in `DATABASE_URL` match the `POSTGRES_*` variables.

### 2. Start PostgreSQL Container

```bash
docker compose up -d postgres
```

**That's it!** Docker Compose automatically:
- Creates the database specified in `POSTGRES_DB`
- Creates the user specified in `POSTGRES_USER` with `POSTGRES_PASSWORD`
- Sets up all required permissions
- Waits for PostgreSQL to be ready

### 3. Verify Setup (Optional)

```bash
./scripts/verify_postgres.sh
```

This confirms:
- PostgreSQL is running
- Database and user exist
- Connection works
- Shows current configuration

---

## Detailed Configuration

### Database Credentials Structure

Your `.env` file should have these variables:

```bash
# PostgreSQL credentials (used by docker-compose.yml)
POSTGRES_USER="finetune"           # Database user
POSTGRES_PASSWORD=""  # User password
POSTGRES_DB="finetune_db"          # Database name

# Full connection string (used by the application)
DATABASE_URL="postgresql+asyncpg://finetune:secure_password@postgres:5432/finetune_db"
```

### DATABASE_URL Format

```
postgresql+asyncpg://USER:PASSWORD@HOST:PORT/DATABASE
                     ↓     ↓         ↓     ↓    ↓
                     └─────┴─────────┴─────┴────┴─── Must match POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB
```

**Components:**
- `postgresql+asyncpg` - Database driver (do not change)
- `USER` - Database username (must match `POSTGRES_USER`)
- `PASSWORD` - Database password (must match `POSTGRES_PASSWORD`)
- `HOST` - Database host (`localhost` for local API, `postgres` for Docker)
- `PORT` - Database port (default: `5432`)
- `DATABASE` - Database name (must match `POSTGRES_DB`)

### Deployment-Specific DATABASE_URL

#### Docker Compose (Recommended - both API and PostgreSQL)
```bash
DATABASE_URL="postgresql+asyncpg://finetune:password@postgres:5432/finetune_db"
#                                                      ↑
#                                              Use container name
```

#### Local API + Docker PostgreSQL
```bash
DATABASE_URL="postgresql+asyncpg://finetune:password@localhost:5432/finetune_db"
```

---

## How It Works

### Automatic Initialization by Docker Compose

When you run `docker compose up -d postgres`, Docker automatically:

1. **Reads Environment Variables** from `.env` file:
   - `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`

2. **Creates Database Objects** on first startup:
   - Creates the database user
   - Creates the database
   - Grants all necessary permissions

3. **Persists Data** in Docker volume:
   - Data survives container restarts
   - Located in `postgres_data` volume

5. **Sets Permissions**
   - Grants all privileges on database
   - Grants schema permissions

6. **Verifies**
   - Tests connection with new credentials
   - Displays connection string for `.env`

### Script Output

Successful run looks like:

```
========================================
4. **No Manual Commands Needed**:
   - Everything is automatic!
   - No SQL commands to run
   - No manual user creation

### What Happens on First Startup

When PostgreSQL container starts for the first time:

```
Docker reads .env → POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB
         ↓
PostgreSQL creates user and database automatically
         ↓
Grants all permissions to the user
         ↓
Ready to accept connections!
```

**Example Output:**
```
Creating finetune-postgres ... done
Waiting for PostgreSQL to be ready...
✓ PostgreSQL is ready!
✓ Database 'finetune_db' created automatically
✓ User 'finetune' created automatically
✓ All permissions granted
```

---

## Verification

### Using verify_postgres.sh

```bash
./scripts/verify_postgres.sh
```

**Checks:**
- Container status
- Configuration from `.env`
- Connection validity
- Table existence

**Output:**
```
✓ PostgreSQL container is running
✓ Configuration loaded from .env
✓ Connection successful

DATABASE_URL="postgresql+asyncpg://finetune:finetune123@postgres:5432/finetune_db"
```

### Manual Verification

#### Check Container

```bash
docker compose ps postgres
```

Expected: Status should be "Up"

#### Connect to PostgreSQL

```bash
docker compose exec postgres psql -U finetune -d finetune_db
```

#### List Databases

```bash
docker compose exec -T postgres psql -U finetune -c "\l"
```

#### Test Connection from Application

```bash
# From your application directory
python -c "from app.database import engine; print('Connection OK')"
```

---

## Troubleshooting

### Container Not Running

**Problem:** `PostgreSQL container is not running`

**Solution:**
```bash
# Start the container
docker compose up -d postgres

# Check logs
docker compose logs postgres
```

### Connection Refused

**Problem:** `Connection refused` or `could not connect`

**Causes:**
1. PostgreSQL still starting up (wait 10-20 seconds)
2. Wrong credentials in `.env`
3. Port 5432 already in use

**Solution:**
```bash
# Wait for PostgreSQL to fully start
sleep 10
./scripts/verify_postgres.sh

# Check what's using port 5432
sudo lsof -i :5432

# Check PostgreSQL logs
docker compose logs postgres
```

### Credentials Mismatch

**Problem:** `authentication failed` or `password authentication failed`

**Cause:** Mismatch between `.env` credentials and `DATABASE_URL`

**Solution:**

1. Check `.env`:
```bash
cat .env | grep -E "POSTGRES_|DATABASE_URL"
```

2. Ensure they match:
```bash
POSTGRES_USER="finetune"
POSTGRES_PASSWORD="mypass123"
DATABASE_URL="postgresql+asyncpg://finetune:mypass123@postgres:5432/finetune_db"
#                                    ↑        ↑
#                                    Must match above
```

3. Restart PostgreSQL to apply changes:
```bash
docker compose restart postgres
```

### Database Already Exists

**Not a problem!** Docker only creates the database on first startup. Subsequent restarts reuse the existing database.

If you want to start fresh:
```bash
# WARNING: This deletes all data!
docker compose down -v
docker compose up -d postgres
```

### Permission Denied

**Problem:** `permission denied for schema public`

**Cause:** Database was created outside Docker's automatic initialization

**Solution:**
```bash
# Connect and grant permissions manually
docker compose exec postgres psql -U postgres -d finetune_db -c "GRANT ALL ON SCHEMA public TO finetune;"
```

### Container Keeps Restarting

**Check logs:**
```bash
docker compose logs postgres
```

**Common causes:**
- Port 5432 already in use
- Data corruption
- Insufficient disk space

**Solution:**
```bash
# Stop and remove (WARNING: deletes data)
docker compose down -v

# Start fresh
docker compose up -d postgres
```

---

## Advanced Operations

### Change Database Password

1. Update `.env`:
```bash
POSTGRES_PASSWORD=""
DATABASE_URL="postgresql+asyncpg://finetune:new_secure_password@postgres:5432/finetune_db"
```

2. Recreate PostgreSQL container:
```bash
docker compose down postgres
docker compose up -d postgres
```

### Backup Database

```bash
# Backup to file
docker compose exec postgres pg_dump -U finetune finetune_db > backup.sql

# Restore from file
docker compose exec -T postgres psql -U finetune -d finetune_db < backup.sql
```

### Reset Database

```bash
# WARNING: Deletes all data and volumes!
docker compose down -v

# Restart with fresh database (auto-creates everything)
docker compose up -d postgres
```

### Access PostgreSQL CLI

```bash
# As finetune user
docker compose exec postgres psql -U finetune -d finetune_db

# As postgres admin
docker compose exec postgres psql -U postgres

# Common commands:
\l          # List databases
\du         # List users
\dt         # List tables
\q          # Quit
```

---

## Docker Compose Configuration

The `docker-compose.yml` reads from `.env` and automatically configures PostgreSQL:

```yaml
postgres:
  image: postgres:15-alpine
  env_file:
    - .env
  environment:
    - POSTGRES_USER=${POSTGRES_USER}      # From .env
    - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}  # From .env
    - POSTGRES_DB=${POSTGRES_DB}          # From .env
  ports:
    - "5432:5432"
  volumes:
    - postgres_data:/var/lib/postgresql/data
  healthcheck:
    test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-finetune}"]
    interval: 10s
    timeout: 5s
    retries: 5
```

Docker automatically creates the database and user based on these environment variables on first startup.

---

## Best Practices

1. **Use Strong Passwords**
   ```bash
   # Generate secure password
   openssl rand -base64 24
   ```

2. **Keep .env Secure**
   - Never commit `.env` to git
   - Use different credentials for production
   - Set restrictive file permissions: `chmod 600 .env`

3. **Regular Backups**
   ```bash
   # Automated backup script
   docker compose exec postgres pg_dump -U finetune finetune_db > backup_$(date +%Y%m%d).sql
   ```

4. **Monitor Disk Space**
   ```bash
   docker system df
   ```

5. **Regular Updates**
   ```bash
   # Update PostgreSQL image
   docker compose pull postgres
   docker compose up -d postgres
   ```

---

## FAQ

**Q: Do I need to run a setup script every time I restart?**
A: No! Docker Compose handles everything automatically. Just `docker compose up -d postgres`.

**Q: Can I use an existing PostgreSQL instance?**
A: Yes, just update `DATABASE_URL` in `.env` to point to your instance.

**Q: What if I want a different database name?**
A: Change `POSTGRES_DB` and update `DATABASE_URL` in `.env`, then restart: `docker compose restart postgres`.

**Q: How do I change the password after setup?**
A: Update `.env` and run: `docker compose down && docker compose up -d postgres`.

**Q: How do I completely remove PostgreSQL?**
A:
```bash
docker compose down -v  # Removes containers and volumes
```

**Q: Why use POSTGRES_* variables instead of DB_*?**
A: `POSTGRES_*` are the standard PostgreSQL Docker image variables. This eliminates duplication and confusion.

---

## Migration from Old Setup

If you have the old configuration with `DB_NAME`, `DB_USER`, `DB_PASSWORD`:

### Update .env file:
```bash

# NEW (use these instead)
POSTGRES_USER="finetune"
POSTGRES_PASSWORD=""
POSTGRES_DB="finetune_db"
```

### Update DATABASE_URL:
```bash
# Change host from localhost to postgres for container networking
DATABASE_URL="postgresql+asyncpg://POSTGRES_USER:POSTGRES_PASSWORD@postgres:5432/finetune_db"
```

### Restart services:
```bash
docker compose down
docker compose up -d
```

---

## Next Steps

After PostgreSQL is set up:

1. ✅ Verify `.env` has correct `DATABASE_URL`
2. ✅ Start the fine-tuning API: `docker compose up -d finetune-api`
3. ✅ Check API logs: `docker compose logs -f finetune-api`

See main [README.md](README.md) for application setup.

---

**Need Help?** Check the troubleshooting section above or open an issue.
