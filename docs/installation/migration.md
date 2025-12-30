# Migration Guide

This guide explains how to migrate Claude Code Proxy between different deployment methods while preserving your OAuth accounts.

## Overview

All deployment methods share the same OAuth account format, making migration seamless:

```json
{
  "schema_version": "1.0.0",
  "accounts": [
    {
      "id": "uuid-v4",
      "email": "user@example.com",
      "access_token": "sk-ant-oat01-...",
      "refresh_token": "sk-ant-ort01-...",
      "expires_at": 1747909518727,
      "created_at": 1747909518727,
      "updated_at": 1747909518727,
      "is_active": true
    }
  ]
}
```

---

## Quick Migration

### Step 1: Export from Current Installation

**Via Web UI**:
1. Open `http://your-current-installation/accounts`
2. Click **"Export Accounts"**
3. Save JSON file

**Via API**:
```bash
curl http://your-current-installation/api/accounts > accounts-backup.json
```

### Step 2: Install New Deployment

Choose your target method:
- [Docker](#migrate-to-docker)
- [Homebrew](#migrate-to-homebrew)
- [Cloud Platform](#migrate-to-cloud)
- [Windows/Chocolatey](#migrate-to-windows)
- [Linux/Snap](#migrate-to-linux)
- [Kubernetes](#migrate-to-kubernetes)
- [Standalone Binary](#migrate-to-binary)

### Step 3: Import to New Installation

**Via Web UI**:
1. Open `http://your-new-installation/accounts`
2. Click **"Import Accounts"**
3. Select `accounts-backup.json`
4. Click **"Import"**

**Via API**:
```bash
curl -X POST http://your-new-installation/api/accounts/import \
  -H "Content-Type: application/json" \
  -d @accounts-backup.json
```

### Step 4: Verify Migration

```bash
curl http://your-new-installation/api/accounts
```

Expected response:
```json
{
  "schema_version": "1.0.0",
  "accounts": [
    {
      "id": "...",
      "email": "user@example.com",
      "is_active": true
    }
  ]
}
```

---

## Migration Scenarios

### Migrate to Docker

**From**: Any method
**To**: Docker Compose

```bash
# 1. Export from current installation
curl http://current-installation/api/accounts > accounts.json

# 2. Install Docker version
curl -fsSL https://joachimbrindeau.github.io/claude-proxy-multi/install.sh | bash

# 3. Wait for service to start
until curl -f http://localhost:8000/health; do sleep 2; done

# 4. Import accounts
curl -X POST http://localhost:8000/api/accounts/import \
  -H "Content-Type: application/json" \
  -d @accounts.json

# 5. Verify
curl http://localhost:8000/api/accounts
```

**Data location**: Docker volume `claude-code-proxy-config:/config/accounts.json`

---

### Migrate to Homebrew

**From**: Any method
**To**: Homebrew (macOS)

```bash
# 1. Export from current installation
curl http://current-installation/api/accounts > accounts.json

# 2. Install via Homebrew
brew install joachimbrindeau/claude-code-proxy/claude-code-proxy
brew services start claude-code-proxy

# 3. Wait for service to start
until curl -f http://localhost:8080/health; do sleep 2; done

# 4. Import via web UI
open http://localhost:8080/accounts
# Click "Import Accounts" and select accounts.json

# 5. Verify
curl http://localhost:8080/api/accounts
```

**Data location**: `/opt/homebrew/var/claude-code-proxy/data/accounts.json`

---

### Migrate to Cloud

**From**: Any method
**To**: Railway/Render/Fly.io

#### Railway

```bash
# 1. Export accounts
curl http://current-installation/api/accounts > accounts.json

# 2. Deploy to Railway (one-click via button in README)
# 3. Wait for deployment to complete

# 4. Import accounts
curl -X POST https://your-app.railway.app/api/accounts/import \
  -H "Content-Type: application/json" \
  -d @accounts.json
```

#### Render

```bash
# 1. Export accounts
curl http://current-installation/api/accounts > accounts.json

# 2. Deploy to Render (one-click via button in README)
# 3. Wait for deployment to complete

# 4. Import accounts
curl -X POST https://your-app.onrender.com/api/accounts/import \
  -H "Content-Type: application/json" \
  -d @accounts.json
```

#### Fly.io

```bash
# 1. Export accounts
curl http://current-installation/api/accounts > accounts.json

# 2. Deploy to Fly.io
flyctl launch --config packaging/cloud/fly.toml

# 3. Get app URL
flyctl status

# 4. Import accounts
curl -X POST https://your-app.fly.dev/api/accounts/import \
  -H "Content-Type: application/json" \
  -d @accounts.json
```

**Data location**: Persistent volume at `/data/accounts.json`

---

### Migrate to Windows

**From**: Any method
**To**: Windows/Chocolatey

```powershell
# 1. Export from current installation
curl http://current-installation/api/accounts -o accounts.json

# 2. Install via Chocolatey
choco install claude-code-proxy
Start-Service claude-code-proxy

# 3. Wait for service to start
Start-Sleep -Seconds 5

# 4. Import via web UI
Start-Process http://localhost:8000/accounts
# Click "Import Accounts" and select accounts.json

# 5. Verify
curl http://localhost:8000/api/accounts
```

**Data location**: `%APPDATA%\claude-code-proxy\data\accounts.json`

---

### Migrate to Linux

**From**: Any method
**To**: Snap (Linux)

```bash
# 1. Export from current installation
curl http://current-installation/api/accounts > accounts.json

# 2. Install via Snap
sudo snap install claude-code-proxy

# 3. Wait for service to start
until curl -f http://localhost:8000/health; do sleep 2; done

# 4. Import accounts
curl -X POST http://localhost:8000/api/accounts/import \
  -H "Content-Type: application/json" \
  -d @accounts.json

# 5. Verify
curl http://localhost:8000/api/accounts
```

**Data location**: `$SNAP_USER_COMMON/data/accounts.json`

---

### Migrate to Kubernetes

**From**: Any method
**To**: Helm chart (Kubernetes)

```bash
# 1. Export from current installation
curl http://current-installation/api/accounts > accounts.json

# 2. Install Helm chart
helm repo add claude-code-proxy https://joachimbrindeau.github.io/claude-proxy-multi
helm install my-proxy claude-code-proxy/claude-code-proxy

# 3. Wait for pod to be ready
kubectl wait --for=condition=ready pod -l app=claude-code-proxy --timeout=300s

# 4. Port forward to access
kubectl port-forward svc/claude-code-proxy 8000:8000 &

# 5. Import accounts
curl -X POST http://localhost:8000/api/accounts/import \
  -H "Content-Type: application/json" \
  -d @accounts.json

# 6. Verify
curl http://localhost:8000/api/accounts
```

**Data location**: PersistentVolumeClaim mounted at `/data/accounts.json`

---

### Migrate to Binary

**From**: Any method
**To**: Standalone executable

```bash
# 1. Export from current installation
curl http://current-installation/api/accounts > accounts.json

# 2. Download binary for your platform
wget https://github.com/joachimbrindeau/claude-proxy-multi/releases/latest/download/claude-code-proxy-linux-amd64

# 3. Make executable and run
chmod +x claude-code-proxy-linux-amd64
./claude-code-proxy-linux-amd64 &

# 4. Wait for startup
sleep 5

# 5. Import accounts
curl -X POST http://localhost:8000/api/accounts/import \
  -H "Content-Type: application/json" \
  -d @accounts.json

# 6. Verify
curl http://localhost:8000/api/accounts
```

**Data location**: `./data/accounts.json` (current directory)

---

## Import Behavior

### Merge Strategy

The import process uses a **merge strategy**:

1. **Existing accounts** (same email) are **updated** with new tokens
2. **New accounts** (not in current installation) are **added**
3. **Unlisted accounts** (not in import file) are **preserved**

**Example**:

Current installation:
```json
{
  "accounts": [
    {"email": "alice@example.com"},
    {"email": "bob@example.com"}
  ]
}
```

Import file:
```json
{
  "accounts": [
    {"email": "alice@example.com"},  // Will UPDATE alice
    {"email": "charlie@example.com"} // Will ADD charlie
  ]
}
```

Result after import:
```json
{
  "accounts": [
    {"email": "alice@example.com"},   // Updated
    {"email": "bob@example.com"},     // Preserved
    {"email": "charlie@example.com"}  // Added
  ]
}
```

### Validation

Import validates:
- ✅ Schema version compatibility
- ✅ UUID v4 format for account IDs
- ✅ Valid email addresses
- ✅ JWT token format (3 parts separated by dots)
- ✅ Timestamp validity (positive integers)
- ✅ No duplicate emails in import file

Invalid accounts are rejected with detailed error messages.

---

## Advanced Scenarios

### Zero-Downtime Migration

Migrate without service interruption:

1. **Install new deployment** alongside current one (different port)
2. **Import accounts** to new deployment
3. **Update client configurations** to point to new endpoint
4. **Monitor** both deployments for 24 hours
5. **Decommission** old deployment

**Example**:

```bash
# Current: Docker on port 8000
# New: Homebrew on port 8080

# 1. Export and import (as shown above)

# 2. Update clients gradually
# Old: http://localhost:8000/api/v1/messages
# New: http://localhost:8080/api/v1/messages

# 3. Monitor both
curl http://localhost:8000/health
curl http://localhost:8080/health

# 4. After 24 hours, stop old deployment
docker-compose down
```

### Multi-Region Migration

Migrate to cloud with multiple regions:

```bash
# 1. Deploy to primary region (e.g., US)
flyctl launch --region lax

# 2. Import accounts to primary
curl -X POST https://us.your-app.fly.dev/api/accounts/import \
  -H "Content-Type: application/json" \
  -d @accounts.json

# 3. Deploy to secondary region (e.g., EU)
flyctl scale regions add ams

# Accounts automatically sync via shared volume
```

### Disaster Recovery

Automate regular backups:

```bash
# Add to cron (runs daily at 2 AM)
0 2 * * * curl http://localhost:8000/api/accounts > ~/backups/accounts-$(date +\%Y\%m\%d).json

# Retention (keep last 30 days)
0 3 * * * find ~/backups -name "accounts-*.json" -mtime +30 -delete
```

### Bulk Migration (Multiple Installations)

Migrate multiple proxies to consolidated cloud deployment:

```bash
#!/bin/bash
# migrate-all.sh

INSTALLATIONS=(
  "http://proxy1.internal:8000"
  "http://proxy2.internal:8000"
  "http://proxy3.internal:8000"
)

NEW_INSTALLATION="https://consolidated.railway.app"

for install in "${INSTALLATIONS[@]}"; do
  echo "Exporting from $install..."
  curl "$install/api/accounts" > "backup-$(echo $install | md5sum | cut -d' ' -f1).json"
done

echo "Importing to $NEW_INSTALLATION..."
for backup in backup-*.json; do
  curl -X POST "$NEW_INSTALLATION/api/accounts/import" \
    -H "Content-Type: application/json" \
    -d "@$backup"
done

echo "Migration complete!"
```

---

## Troubleshooting

### Import Fails with "Invalid Schema Version"

**Problem**: Schema version mismatch

**Solution**: Ensure both installations are on compatible versions

```bash
# Check source version
curl http://source/health | jq .version

# Check target version
curl http://target/health | jq .version

# Upgrade target if needed
# Docker: docker-compose pull && docker-compose up -d
# Homebrew: brew upgrade claude-code-proxy
# Chocolatey: choco upgrade claude-code-proxy
```

### Import Fails with "Duplicate Email"

**Problem**: Import file contains duplicate emails

**Solution**: Remove duplicates from export file

```bash
# Detect duplicates
cat accounts.json | jq '.accounts[].email' | sort | uniq -d

# Remove duplicates (keeps first occurrence)
cat accounts.json | jq '.accounts |= unique_by(.email)' > accounts-clean.json
```

### Tokens Expired After Import

**Problem**: Access tokens expired during migration

**Solution**: Tokens automatically refresh on first use

```bash
# Trigger refresh by making test request
curl http://new-installation/api/v1/messages \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-sonnet-4-20250514",
    "max_tokens": 10,
    "messages": [{"role": "user", "content": "test"}]
  }'

# Check account status
curl http://new-installation/api/accounts
```

### Import Shows Success but No Accounts

**Problem**: Permissions or path issues

**Solution**: Check data directory permissions

```bash
# Docker
docker exec claude-code-proxy ls -la /config/

# Homebrew
ls -la /opt/homebrew/var/claude-code-proxy/data/

# Snap
ls -la $SNAP_USER_COMMON/data/

# Windows
dir %APPDATA%\claude-code-proxy\data
```

---

## Best Practices

### Pre-Migration Checklist

- [ ] Export accounts from source installation
- [ ] Verify export file contains all expected accounts
- [ ] Test import on non-production environment first
- [ ] Document source and target installation URLs
- [ ] Plan rollback procedure

### During Migration

- [ ] Keep source installation running during import
- [ ] Monitor health endpoints on both installations
- [ ] Verify account count matches before/after
- [ ] Test authentication on target installation
- [ ] Update client configurations gradually

### Post-Migration

- [ ] Monitor logs for authentication errors
- [ ] Verify all accounts are active
- [ ] Test rotation is working
- [ ] Update documentation with new endpoint
- [ ] Archive source installation backup

### Security Considerations

- **Encrypt backups** containing OAuth tokens
- **Delete temporary files** after import
- **Rotate tokens** if backup file is compromised
- **Use HTTPS** for cloud deployments
- **Restrict access** to accounts API endpoint

---

## Migration Matrix

| From → To | Docker | Homebrew | Cloud | Windows | Linux | Kubernetes | Binary |
|-----------|--------|----------|-------|---------|-------|------------|--------|
| **Docker** | - | ✅ Direct | ✅ Direct | ✅ Direct | ✅ Direct | ✅ Direct | ✅ Direct |
| **Homebrew** | ✅ Direct | - | ✅ Direct | ✅ Direct | ✅ Direct | ✅ Direct | ✅ Direct |
| **Cloud** | ✅ Direct | ✅ Direct | ✅ Same cloud | ✅ Direct | ✅ Direct | ✅ Direct | ✅ Direct |
| **Windows** | ✅ Direct | ✅ Direct | ✅ Direct | - | ❌ Different OS | ✅ Direct | ✅ Direct |
| **Linux** | ✅ Direct | ✅ Direct | ✅ Direct | ❌ Different OS | - | ✅ Direct | ✅ Direct |
| **Kubernetes** | ✅ Direct | ✅ Direct | ✅ Direct | ✅ Direct | ✅ Direct | - | ✅ Direct |
| **Binary** | ✅ Direct | ✅ Direct | ✅ Direct | ✅ Direct | ✅ Direct | ✅ Direct | - |

**Direct**: Export/import via API works seamlessly
**Same cloud**: May support volume migration
**Different OS**: Requires fresh installation (accounts migrate, but binary doesn't)

---

## Next Steps

After successful migration:

- 📖 [Installation Guides](./README.md)
- 🔧 [Configuration Guide](../configuration/README.md)
- 🐛 [Troubleshooting](../troubleshooting.md)
- 💬 [Get Help](https://github.com/joachimbrindeau/claude-proxy-multi/issues)
