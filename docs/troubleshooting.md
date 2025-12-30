# Troubleshooting Guide

Common issues and solutions for Claude Code Proxy across all deployment methods.

## Quick Diagnostics

Run these checks first:

```bash
# 1. Check service health
curl http://localhost:8000/health

# Expected response:
# {"status": "healthy", "version": "0.1.0"}

# 2. Check if port is listening
# macOS/Linux:
lsof -i :8000
# Windows:
netstat -ano | findstr :8000

# 3. Check service logs
# Docker:
docker-compose logs -f
# Homebrew:
tail -f /opt/homebrew/var/log/claude-code-proxy/stdout.log
# Windows:
Get-EventLog -LogName Application -Source "claude-code-proxy" -Newest 50
# Snap:
snap logs claude-code-proxy -f
```

---

## Installation Issues

### Port Already in Use

**Symptoms**:
- Error: `Address already in use: bind`
- Service won't start
- Health check times out

**Diagnosis**:

```bash
# Find what's using the port
# macOS/Linux:
lsof -i :8000
# Windows:
Get-NetTCPConnection -LocalPort 8000
```

**Solutions**:

**Option 1**: Stop the conflicting service

```bash
# macOS/Linux:
lsof -ti:8000 | xargs kill
# Windows:
Stop-Process -Id <PID> -Force
```

**Option 2**: Change Claude Code Proxy port

```bash
# Docker - edit docker-compose.yml:
ports:
  - '9000:8000'  # External:Internal

# Homebrew - edit service:
brew services stop claude-code-proxy
vim ~/Library/LaunchAgents/homebrew.mxcl.claude-code-proxy.plist
# Change --port 8080 to --port 9000
brew services start claude-code-proxy

# Windows - reconfigure service:
Stop-Service claude-code-proxy
sc.exe config claude-code-proxy binPath= "\"C:\...\claude-code-proxy-api.exe\" --host 0.0.0.0 --port 9000"
Start-Service claude-code-proxy
```

---

### Permission Denied

**Symptoms**:
- Error: `Permission denied` when accessing files
- Cannot write to data directory
- Service fails to start

**Diagnosis**:

```bash
# Check data directory permissions
# Docker:
docker exec claude-code-proxy ls -la /config/

# Homebrew:
ls -la /opt/homebrew/var/claude-code-proxy/

# Windows:
icacls %APPDATA%\claude-code-proxy
```

**Solutions**:

```bash
# Docker - fix container permissions:
docker-compose down
docker-compose up -d

# Homebrew - fix directory ownership:
sudo chown -R $(whoami) /opt/homebrew/var/claude-code-proxy/

# Windows - grant full control:
icacls %APPDATA%\claude-code-proxy /grant %USERNAME%:F /T

# Snap - check plugs:
snap connections claude-code-proxy
# If home plug disconnected:
sudo snap connect claude-code-proxy:home
```

---

### Python Module Not Found

**Symptoms**:
- Error: `ModuleNotFoundError: No module named 'claude_code_proxy'`
- Import errors in logs

**Solutions**:

```bash
# Docker - rebuild image:
docker-compose pull
docker-compose up -d

# Homebrew - reinstall:
brew reinstall claude-code-proxy
brew services restart claude-code-proxy

# Windows - reinstall package:
choco uninstall claude-code-proxy
choco install claude-code-proxy

# Manual Python install:
pip install --upgrade claude-code-proxy
```

---

## Network Issues

### Cannot Access Web UI

**Symptoms**:
- Browser can't load `http://localhost:8000`
- Connection refused or timeout

**Diagnosis**:

```bash
# 1. Check if service is running
# Docker:
docker-compose ps
# Homebrew:
brew services list | grep claude-code-proxy
# Windows:
Get-Service claude-code-proxy

# 2. Check if port is accessible
curl http://localhost:8000/health

# 3. Try different addresses
curl http://127.0.0.1:8000/health
curl http://0.0.0.0:8000/health
```

**Solutions**:

**If service not running**:
```bash
# Start the service (method-specific)
docker-compose up -d
brew services start claude-code-proxy
Start-Service claude-code-proxy
```

**If port not accessible**:
```bash
# Check firewall
# macOS:
sudo /usr/libexec/ApplicationFirewall/socketfilterfw --getglobalstate

# Linux:
sudo ufw status
sudo ufw allow 8000/tcp

# Windows:
New-NetFirewallRule -DisplayName "Claude Code Proxy" -Direction Inbound -LocalPort 8000 -Protocol TCP -Action Allow
```

**If using remote access**:
```bash
# Ensure server binds to 0.0.0.0, not localhost
# Check logs for:
# "Server running on http://0.0.0.0:8000"  ✅ Good
# "Server running on http://127.0.0.1:8000" ❌ Localhost only
```

---

### Slow Response Times

**Symptoms**:
- Web UI loads slowly
- API requests timeout
- High latency

**Diagnosis**:

```bash
# Check response time
time curl http://localhost:8000/health

# Check resource usage
# Docker:
docker stats claude-code-proxy

# System resources:
top  # Linux/macOS
Get-Process | Sort-Object CPU -Descending | Select-Object -First 10  # Windows
```

**Solutions**:

```bash
# 1. Increase resources (Docker):
# Edit docker-compose.yml:
services:
  claude-code-proxy:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 1G

# 2. Reduce log level:
# Set environment variable:
SERVER__LOG_LEVEL=WARNING

# 3. Check network connectivity to Claude API:
curl -w "@-" -o /dev/null -s https://api.anthropic.com/v1/models <<< "
    time_namelookup:  %{time_namelookup}s
         time_connect:  %{time_connect}s
      time_appconnect:  %{time_appconnect}s
     time_pretransfer:  %{time_pretransfer}s
        time_redirect:  %{time_redirect}s
   time_starttransfer:  %{time_starttransfer}s
                      ----------
           time_total:  %{time_total}s
"
```

---

## Authentication Issues

### OAuth Flow Fails

**Symptoms**:
- Cannot complete OAuth authorization
- "Invalid authorization code" error
- Redirect fails

**Diagnosis**:

```bash
# Check if OAuth endpoint is accessible
curl http://localhost:8000/oauth/authorize

# Check logs for OAuth errors
# Docker:
docker-compose logs | grep oauth
```

**Solutions**:

1. **Clear browser cookies** and retry
2. **Use incognito/private browsing** to avoid cached credentials
3. **Check if already logged into Claude** in the same browser
4. **Verify the full authorization URL** was copied (no truncation)
5. **Try different browser** if issue persists

---

### Token Refresh Failures

**Symptoms**:
- Error: `Failed to refresh token`
- Accounts show as inactive
- 401 Unauthorized errors

**Diagnosis**:

```bash
# Check account status
curl http://localhost:8000/api/accounts | jq '.accounts[] | {email, is_active, expires_at}'

# Check if token is expired (Unix timestamp)
date +%s  # Current time
# Compare with expires_at value
```

**Solutions**:

```bash
# 1. Manually trigger refresh via API request:
curl http://localhost:8000/api/v1/messages \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-sonnet-4-20250514",
    "max_tokens": 10,
    "messages": [{"role": "user", "content": "test"}]
  }'

# 2. Re-authorize account via web UI:
# Open http://localhost:8000/accounts
# Click "Re-authorize" on the failing account

# 3. Remove and re-add account:
# Delete account via web UI
# Add fresh account via OAuth flow
```

---

### Rate Limit Errors (429)

**Symptoms**:
- Error: `429 Too Many Requests`
- Requests fail even with multiple accounts
- Rotation not working

**Diagnosis**:

```bash
# Check rotation status
curl http://localhost:8000/status | jq

# Check account count
curl http://localhost:8000/api/accounts | jq '.accounts | length'

# Check rotation enabled
# Look for: CCPROXY_ROTATION_ENABLED=true
```

**Solutions**:

**Enable rotation** (if disabled):
```bash
# Docker - edit docker-compose.yml:
environment:
  - CCPROXY_ROTATION_ENABLED=true

# Restart:
docker-compose restart

# Homebrew/Windows - set environment variable and restart
```

**Add more accounts**:
```bash
# Add accounts via web UI
open http://localhost:8000/accounts
# Click "Add Account" for each Claude subscription
```

**Check rate limit status**:
```bash
# Each Claude Max subscription has limits
# Monitor usage across accounts
curl http://localhost:8000/status | jq '.rotation'
```

---

## Data Issues

### Accounts Not Persisting

**Symptoms**:
- Accounts disappear after restart
- Need to re-add accounts frequently
- Import doesn't save

**Diagnosis**:

```bash
# Check if accounts file exists
# Docker:
docker exec claude-code-proxy ls -la /config/accounts.json

# Homebrew:
ls -la /opt/homebrew/var/claude-code-proxy/data/accounts.json

# Windows:
dir %APPDATA%\claude-code-proxy\data\accounts.json

# Snap:
ls -la ~/snap/claude-code-proxy/common/data/accounts.json
```

**Solutions**:

**Docker - check volume mount**:
```bash
docker inspect claude-code-proxy | jq '.[0].Mounts'
# Verify /config is mounted to named volume

# If missing, recreate with volume:
docker-compose down
docker-compose up -d
```

**Homebrew - check directory**:
```bash
# Ensure data directory exists
mkdir -p /opt/homebrew/var/claude-code-proxy/data
chmod 700 /opt/homebrew/var/claude-code-proxy/data
```

**Windows - check permissions**:
```powershell
# Ensure directory exists and is writable
$dataDir = "$env:APPDATA\claude-code-proxy\data"
if (!(Test-Path $dataDir)) {
    New-Item -ItemType Directory -Path $dataDir -Force
}
```

---

### Corrupt Accounts File

**Symptoms**:
- Error: `Failed to parse accounts.json`
- Service won't start
- Web UI shows error

**Solutions**:

```bash
# 1. Backup current file
# Docker:
docker cp claude-code-proxy:/config/accounts.json ./accounts.backup.json

# Homebrew:
cp /opt/homebrew/var/claude-code-proxy/data/accounts.json ~/accounts.backup.json

# 2. Validate JSON syntax
cat accounts.json | jq .
# If invalid, manually fix or restore from backup

# 3. If unfixable, start fresh:
# Remove corrupt file
rm accounts.json  # (method-specific path)

# Restart service (creates new empty file)
# Re-add accounts via web UI
```

---

## Service Management

### Service Won't Start

**Symptoms**:
- Start command fails
- Process exits immediately
- Health check never succeeds

**Diagnosis**:

```bash
# Check detailed error messages
# Docker:
docker-compose logs --tail=100

# Homebrew:
tail -100 /opt/homebrew/var/log/claude-code-proxy/stderr.log

# Windows:
Get-EventLog -LogName Application -Source "claude-code-proxy" -Newest 10 | Format-List

# Snap:
snap logs claude-code-proxy --lines=100
```

**Common causes and solutions**:

**Missing Python dependencies**:
```bash
# Reinstall (method-specific)
```

**Port conflict**:
```bash
# Change port (see "Port Already in Use" section)
```

**Insufficient permissions**:
```bash
# Fix permissions (see "Permission Denied" section)
```

**Configuration errors**:
```bash
# Check environment variables
# Docker:
docker inspect claude-code-proxy | jq '.[0].Config.Env'

# Verify no typos in variable names
```

---

### Service Stops Unexpectedly

**Symptoms**:
- Service runs briefly then stops
- Random crashes
- Memory errors

**Diagnosis**:

```bash
# Check system resources
free -h  # Memory
df -h    # Disk space

# Check for OOM kills
# Linux:
dmesg | grep -i "out of memory"
journalctl -k | grep -i "killed process"

# Docker:
docker stats claude-code-proxy
```

**Solutions**:

```bash
# Increase memory limit
# Docker - edit docker-compose.yml:
services:
  claude-code-proxy:
    deploy:
      resources:
        limits:
          memory: 1G

# Kubernetes - edit values.yaml:
resources:
  limits:
    memory: 1Gi

# Enable automatic restart
# Docker (already enabled by default via restart: unless-stopped)

# Homebrew - service auto-restarts via launchd

# Windows - configure recovery:
sc.exe failure claude-code-proxy reset= 86400 actions= restart/60000
```

---

## Cloud Platform Issues

### Railway Deployment Fails

**Solutions**:

1. **Check build logs** in Railway dashboard
2. **Verify Dockerfile** is in repository root
3. **Ensure volume is attached** (add manually if missing)
4. **Check environment variables** are set correctly

### Render Deployment Fails

**Solutions**:

1. **Verify render.yaml** syntax
2. **Check if disk is attached** (Settings → Disks)
3. **View build logs** in Events tab
4. **Ensure branch** is set to `main` for auto-deploy

### Fly.io Deployment Fails

**Solutions**:

```bash
# Check deployment status
flyctl status

# View logs
flyctl logs

# Verify volume exists
flyctl volumes list

# Check configuration
flyctl config validate

# Redeploy
flyctl deploy
```

---

## Performance Optimization

### High Memory Usage

```bash
# Reduce log verbosity
SERVER__LOG_LEVEL=WARNING

# Disable hot-reload if not needed
CCPROXY_HOT_RELOAD=false

# Limit concurrent connections (Kubernetes/Docker)
# Configure in deployment template
```

### High CPU Usage

```bash
# Check for excessive rotation
# Monitor rotation frequency in logs

# Reduce request rate if possible
# Add more accounts to distribute load
```

---

## Getting Help

If your issue isn't covered here:

1. **Search existing issues**: [GitHub Issues](https://github.com/joachimbrindeau/claude-proxy-multi/issues)
2. **Check logs** and include relevant excerpts
3. **Gather system info**:
   ```bash
   # Version
   curl http://localhost:8000/health | jq .version

   # Deployment method
   docker --version  # or brew --version, choco --version, etc.

   # OS
   uname -a  # Linux/macOS
   systeminfo | findstr /C:"OS"  # Windows
   ```
4. **Create new issue** with:
   - Deployment method
   - Error messages
   - Steps to reproduce
   - Expected vs actual behavior

---

## Common Error Messages

| Error | Cause | Solution |
|-------|-------|----------|
| `Address already in use` | Port conflict | Change port or stop conflicting service |
| `Permission denied` | Insufficient permissions | Fix directory permissions |
| `ModuleNotFoundError` | Missing Python package | Reinstall package |
| `Failed to refresh token` | Expired OAuth credentials | Re-authorize via web UI |
| `429 Too Many Requests` | Rate limit exceeded | Add more accounts or enable rotation |
| `Connection refused` | Service not running | Start service |
| `Invalid authorization code` | OAuth flow interrupted | Retry with fresh authorization |
| `Failed to parse accounts.json` | Corrupt JSON file | Validate and fix or restore backup |
| `Health check failed` | Service unhealthy | Check logs for root cause |
| `Failed to download resource` | Network issue | Check internet connection |

---

## Diagnostic Commands Reference

```bash
# Service Status
docker-compose ps                                    # Docker
brew services list | grep claude-code-proxy          # Homebrew
Get-Service claude-code-proxy                        # Windows
snap services claude-code-proxy                      # Snap
kubectl get pods -l app=claude-code-proxy            # Kubernetes

# Logs
docker-compose logs -f                               # Docker
tail -f /opt/homebrew/var/log/claude-code-proxy/*.log  # Homebrew
Get-EventLog -LogName Application -Source "claude-code-proxy"  # Windows
snap logs claude-code-proxy -f                       # Snap
kubectl logs -l app=claude-code-proxy -f             # Kubernetes

# Health Check
curl http://localhost:8000/health                    # All methods

# Account Status
curl http://localhost:8000/api/accounts | jq         # All methods

# Rotation Status
curl http://localhost:8000/status | jq               # All methods
```

---

## Next Steps

- 📖 [Installation Guides](./installation/README.md)
- 🔧 [Configuration Guide](./configuration/README.md)
- 🔄 [Migration Guide](./installation/migration.md)
- 💬 [GitHub Issues](https://github.com/joachimbrindeau/claude-proxy-multi/issues)
