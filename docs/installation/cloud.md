# Cloud Platform Deployment Guide

Deploy Claude Code Proxy to production-ready cloud platforms with one-click deployment, persistent storage, and automatic scaling.

## Quick Start

**One-click deployment**:

[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/template/claude-code-proxy?referralCode=joachim)

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/joachimbrindeau/claude-proxy-multi)

**Fly.io CLI**:
```bash
flyctl launch --config packaging/cloud/fly.toml
```

**Deployment time**: ~3-5 minutes ⚡

---

## Platform Comparison

| Feature | Railway | Render | Fly.io |
|---------|---------|--------|--------|
| **Deployment** | One-click | One-click | CLI |
| **Free Tier** | $5/month credit | 750 hours/month | 3 shared-cpu-1x VMs |
| **Persistent Storage** | Volumes (extra cost) | Persistent disk (1GB free) | Volumes (3GB free) |
| **Auto-scaling** | ✅ Yes | ✅ Yes | ✅ Yes |
| **HTTPS** | ✅ Auto | ✅ Auto | ✅ Auto |
| **Custom Domain** | ✅ Yes | ✅ Yes | ✅ Yes |
| **Region Choice** | ✅ Global | ✅ Global | ✅ Global |
| **Best For** | Simplicity | Free tier | Edge deployment |

---

## Railway Deployment

### Step 1: Deploy with One Click

Click the Railway button:

[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/template/claude-code-proxy?referralCode=joachim)

### Step 2: Configure Volume (Required)

Railway doesn't automatically create volumes. After deployment:

1. Open your Railway project dashboard
2. Click on your service
3. Go to **Variables** tab
4. Verify `CCPROXY_ACCOUNTS_PATH=/data/accounts.json` is set
5. Go to **Settings** tab
6. Scroll to **Volumes**
7. Click **+ New Volume**
8. Set mount path: `/data`
9. Click **Add**

### Step 3: Redeploy

After adding the volume:
1. Go to **Deployments** tab
2. Click **Redeploy** on latest deployment

### Step 4: Access Web UI

1. Get your deployment URL from Railway dashboard
2. Open `https://your-app.railway.app/accounts`
3. Add Claude accounts via OAuth

### Configuration

Environment variables are set via `packaging/cloud/railway.json`:

```json
{
  "variables": {
    "SERVER__HOST": "0.0.0.0",
    "SERVER__LOG_LEVEL": "INFO",
    "CCPROXY_ACCOUNTS_PATH": "/data/accounts.json",
    "CCPROXY_ROTATION_ENABLED": "true",
    "CCPROXY_HOT_RELOAD": "true"
  }
}
```

**Custom variables**: Set via Railway dashboard → Variables tab

### Persistent Storage

**Volume path**: `/data`
**Accounts path**: `/data/accounts.json`
**Size**: 1GB minimum recommended

### Custom Domain

1. Go to **Settings** → **Domains**
2. Click **+ Custom Domain**
3. Enter your domain (e.g., `claude.example.com`)
4. Add CNAME record to your DNS:
   - Name: `claude`
   - Value: `your-app.railway.app`

### Pricing

- **Free tier**: $5/month credit
- **Compute**: ~$5/month for 1GB RAM instance
- **Volume**: ~$0.25/GB/month

---

## Render Deployment

### Step 1: Deploy with Blueprint

Click the Render button:

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/joachimbrindeau/claude-proxy-multi)

This will:
- Create a new web service
- Configure environment variables
- Attach 1GB persistent disk at `/data`
- Enable health checks
- Set up auto-deploy from main branch

### Step 2: Wait for Build

Build takes ~3-5 minutes. Monitor progress in Render dashboard.

### Step 3: Access Web UI

1. Get your deployment URL from Render dashboard
2. Open `https://your-app.onrender.com/accounts`
3. Add Claude accounts via OAuth

### Configuration

Environment variables from `packaging/cloud/render.yaml`:

```yaml
envVars:
  - key: PORT
    value: 8000
  - key: SERVER__HOST
    value: 0.0.0.0
  - key: SERVER__LOG_LEVEL
    value: INFO
  - key: CCPROXY_ACCOUNTS_PATH
    value: /data/accounts.json
  - key: CCPROXY_ROTATION_ENABLED
    value: true
  - key: CCPROXY_HOT_RELOAD
    value: true
```

**Custom variables**: Dashboard → Environment → Environment Variables

### Persistent Storage

**Disk configuration**:
```yaml
disk:
  name: claude-code-proxy-data
  mountPath: /data
  sizeGB: 1
```

Accounts persist at `/data/accounts.json` across deploys.

### Auto-Deploy

Enabled by default. Pushes to `main` branch trigger automatic redeployment.

**Disable**: Dashboard → Settings → Auto-Deploy → Off

### Custom Domain

1. Go to **Settings** → **Custom Domain**
2. Add your domain (e.g., `claude.example.com`)
3. Add CNAME record to your DNS:
   - Name: `claude`
   - Value: `your-app.onrender.com`

### Pricing

- **Free tier**: 750 hours/month (sleeps after 15min inactivity)
- **Starter**: $7/month (always on, 512MB RAM)
- **Disk**: Free for 1GB

---

## Fly.io Deployment

### Prerequisites

- **Fly.io account** ([Sign up](https://fly.io/app/sign-up))
- **flyctl CLI** ([Install](https://fly.io/docs/hands-on/install-flyctl/))

```bash
# Install flyctl
curl -L https://fly.io/install.sh | sh

# Login
flyctl auth login
```

### Step 1: Launch Application

From repository root:

```bash
flyctl launch --config packaging/cloud/fly.toml
```

This will:
1. Create a new Fly.io app
2. Configure based on `fly.toml`
3. Deploy the application
4. Create volume for persistent storage

### Step 2: Create Volume (if not auto-created)

```bash
flyctl volumes create claude_code_proxy_data --size 1
```

### Step 3: Deploy

```bash
flyctl deploy
```

### Step 4: Access Web UI

```bash
# Get app URL
flyctl status

# Open in browser
flyctl open /accounts
```

### Configuration

Settings from `packaging/cloud/fly.toml`:

```toml
[env]
  PORT = "8000"
  SERVER__HOST = "0.0.0.0"
  SERVER__LOG_LEVEL = "INFO"
  CCPROXY_ACCOUNTS_PATH = "/data/accounts.json"
  CCPROXY_ROTATION_ENABLED = "true"
  CCPROXY_HOT_RELOAD = "true"

[mounts]
  source = "claude_code_proxy_data"
  destination = "/data"
```

**Add custom variables**:
```bash
flyctl secrets set MY_VAR=value
```

### Persistent Storage

**Volume**: 3GB free tier included
**Mount path**: `/data`
**Accounts path**: `/data/accounts.json`

**Backup volume**:
```bash
flyctl volumes list
flyctl volumes snapshots create vol_xxx
```

### Scaling

**Horizontal scaling**:
```bash
# Add more instances
flyctl scale count 2

# Set min/max
flyctl autoscale set min=1 max=3
```

**Vertical scaling**:
```bash
# Increase memory
flyctl scale memory 512

# Change CPU
flyctl scale vm shared-cpu-2x
```

### Custom Domain

```bash
# Add certificate
flyctl certs add claude.example.com

# Get DNS instructions
flyctl certs show claude.example.com
```

### Regions

**List available regions**:
```bash
flyctl platform regions
```

**Change region**:
```toml
# fly.toml
primary_region = "lax"  # Los Angeles
```

**Multi-region**:
```bash
flyctl regions add ams  # Amsterdam
flyctl regions add syd  # Sydney
```

### Pricing

- **Free tier**: 3 shared-cpu-1x VMs, 3GB storage
- **Compute**: ~$0.02/hour for shared-cpu-1x
- **Volume**: $0.15/GB/month

---

## Adding Claude Accounts

All platforms use the same web UI for account management:

1. **Navigate** to `https://your-app-url/accounts`

2. **Click** "Add Account"

3. **Copy** the OAuth URL and open in browser

4. **Sign in** with your Claude account

5. **Copy** the authorization code

6. **Paste** code back in web UI

7. **Done!** Account is active and will rotate automatically

Accounts persist in `/data/accounts.json` across deployments.

---

## Migration Between Platforms

### Export Accounts

From any platform:
```bash
curl https://your-app-url/api/accounts > accounts-backup.json
```

Or via web UI:
1. Open `https://your-app-url/accounts`
2. Click "Export Accounts"
3. Save JSON file

### Import to New Platform

After deploying to new platform:

**Via Web UI**:
1. Open `https://new-app-url/accounts`
2. Click "Import Accounts"
3. Select `accounts-backup.json`

**Via API**:
```bash
curl -X POST https://new-app-url/api/accounts/import \
  -H "Content-Type: application/json" \
  -d @accounts-backup.json
```

---

## Environment Variables

All platforms support these environment variables:

### Server Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | 8000 | HTTP server port (cloud platforms set this) |
| `SERVER__HOST` | 0.0.0.0 | Listen address |
| `SERVER__LOG_LEVEL` | INFO | Logging level (DEBUG, INFO, WARNING, ERROR) |

### Account Management

| Variable | Default | Description |
|----------|---------|-------------|
| `CCPROXY_ACCOUNTS_PATH` | /data/accounts.json | Path to OAuth credentials file |
| `CCPROXY_ROTATION_ENABLED` | true | Enable multi-account rotation |
| `CCPROXY_HOT_RELOAD` | true | Watch accounts file for changes |

### OAuth Configuration

| Variable | Required | Description |
|----------|----------|-------------|
| `CLAUDE_OAUTH_CLIENT_ID` | No | Custom OAuth client ID |
| `CLAUDE_OAUTH_CLIENT_SECRET` | No | Custom OAuth client secret |

---

## Monitoring and Logs

### Railway

**View logs**:
```bash
# Install Railway CLI
npm install -g @railway/cli

# Login
railway login

# Tail logs
railway logs
```

**Dashboard**: Railway → Your Project → Deployments → Logs

### Render

**View logs**: Render Dashboard → Logs tab

**Download logs**:
```bash
curl "https://api.render.com/v1/services/{service-id}/logs" \
  -H "Authorization: Bearer {api-key}"
```

### Fly.io

**View logs**:
```bash
# Real-time logs
flyctl logs

# Historical logs
flyctl logs --limit 1000
```

**Monitoring**:
```bash
flyctl status
flyctl vm status
```

---

## Troubleshooting

### Deployment Fails

**Railway**:
- Check build logs in Deployments tab
- Verify Dockerfile exists in repository
- Ensure environment variables are set

**Render**:
- Check build logs in Events tab
- Verify `render.yaml` is valid
- Check disk is attached correctly

**Fly.io**:
- Run `flyctl logs` to see errors
- Verify `fly.toml` is valid: `flyctl config validate`
- Check volume is created: `flyctl volumes list`

### Cannot Access Web UI

**Check health endpoint**:
```bash
curl https://your-app-url/health
```

**Should return**:
```json
{
  "status": "healthy",
  "version": "0.1.0"
}
```

**If not responding**:
1. Check logs for errors
2. Verify PORT environment variable matches app config
3. Check platform-specific firewall rules

### Accounts Not Persisting

**Railway**:
- Verify volume is attached to `/data`
- Check `CCPROXY_ACCOUNTS_PATH=/data/accounts.json`

**Render**:
- Verify disk is attached in Settings → Disks
- Check mount path is `/data`

**Fly.io**:
- List volumes: `flyctl volumes list`
- Verify mount in `fly.toml`: `destination = "/data"`

### Rate Limit Issues

**Symptoms**: 429 errors even with multiple accounts

**Solutions**:
1. Add more Claude accounts via web UI
2. Verify rotation is enabled: `CCPROXY_ROTATION_ENABLED=true`
3. Check account status: `curl https://your-app-url/api/accounts`
4. Review logs for token refresh errors

### Token Refresh Failures

**Check logs** for refresh errors:
```
ERROR: Failed to refresh token for account@example.com
```

**Solutions**:
1. Re-authorize account via web UI
2. Check OAuth credentials are valid
3. Verify account has active Claude subscription

---

## Security Best Practices

### HTTPS

All platforms provide automatic HTTPS:
- **Railway**: Auto-generated cert
- **Render**: Let's Encrypt cert
- **Fly.io**: Automatic edge termination

### Environment Variables

**Never commit**:
- OAuth tokens
- API keys
- Passwords

**Use platform secret management**:
- Railway: Environment Variables
- Render: Environment Variables (marked secret)
- Fly.io: `flyctl secrets set`

### Access Control

**Restrict by IP** (Fly.io only):
```toml
# fly.toml
[[services.http_checks]]
  allowed_ips = ["1.2.3.4/32"]
```

**Add authentication** via environment:
```bash
# Custom auth header
export PROXY_AUTH_TOKEN=secret-token
```

### OAuth Credentials

**Protect accounts.json**:
- Stored in persistent volume (not in container)
- 700 permissions on /data directory
- Regular backups via export API

---

## Cost Optimization

### Railway

- Use volumes only if needed (adds cost)
- Stop/start service when not in use
- Monitor usage in billing dashboard

### Render

- Use free tier for development
- Suspend service during downtime (Settings → Suspend)
- Upgrade to Starter ($7/month) for always-on

### Fly.io

- Use auto-scaling: `min_machines_running = 0`
- Stop when idle: `auto_stop_machines = true`
- Monitor with: `flyctl scale show`

---

## Performance Tuning

### Memory Allocation

**Railway**: Set in dashboard (512MB - 8GB)

**Render**: Based on plan (Free: 512MB, Starter: 512MB, Standard: 2GB)

**Fly.io**:
```bash
flyctl scale memory 512  # 256, 512, 1024, 2048
```

### CPU

**Fly.io only**:
```bash
flyctl scale vm shared-cpu-1x  # shared-cpu-1x, shared-cpu-2x
```

### Concurrent Connections

**Fly.io** - Edit `fly.toml`:
```toml
[http_service.concurrency]
  type = "connections"
  hard_limit = 50   # Increase for more concurrent requests
  soft_limit = 40
```

---

## Backup and Disaster Recovery

### Automated Backups

**Export accounts daily**:

```bash
# Add to cron
0 2 * * * curl https://your-app-url/api/accounts > ~/backups/accounts-$(date +\%Y\%m\%d).json
```

### Volume Snapshots

**Fly.io**:
```bash
flyctl volumes snapshots create vol_xxx
flyctl volumes snapshots list vol_xxx
```

**Render**: Automatic daily backups (paid plans)

**Railway**: Manual exports only

### Restore from Backup

1. Deploy new instance
2. Import accounts via web UI or API
3. Verify accounts loaded: `curl https://your-app-url/api/accounts`

---

## Next Steps

- 📖 [API Documentation](../api/README.md)
- 🔧 [Configuration Guide](../configuration/README.md)
- 🐳 [Docker Installation](./docker.md)
- 🍺 [Homebrew Installation](./homebrew.md)
- 💬 [Get Help](https://github.com/joachimbrindeau/claude-proxy-multi/issues)
