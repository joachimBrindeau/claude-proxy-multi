# Docker Installation Guide

Install Claude Code Proxy using Docker for the quickest and easiest setup.

## Quick Start

**One-line installation**:
```bash
curl -fsSL https://joachimbrindeau.github.io/ccproxy-api/install.sh | bash
```

That's it! The installer will:
- ✅ Check prerequisites (Docker, Docker Compose)
- ✅ Download the latest configuration
- ✅ Create data directory with proper permissions
- ✅ Start the service
- ✅ Wait for health check
- ✅ Open the web UI in your browser

**Installation time**: ~60 seconds ⚡

---

## Prerequisites

### Required

- **Docker** 20.10.0+ ([Install Docker](https://docs.docker.com/get-docker/))
- **Docker Compose** 2.0.0+ (included with Docker Desktop, or [install separately](https://docs.docker.com/compose/install/))

### Optional

- **curl** - for the one-line installer

---

## Installation Methods

### Method 1: Automated Installer (Recommended)

The installer script handles everything automatically:

```bash
curl -fsSL https://joachimbrindeau.github.io/ccproxy-api/install.sh | bash
```

**What it does**:
1. Verifies Docker and Docker Compose are installed
2. Downloads `docker-compose.yml` from the repository
3. Creates `./data` directory for OAuth credentials
4. Starts services with `docker-compose up -d`
5. Waits for health check (max 60 seconds)
6. Opens http://localhost:8000/accounts in your browser

### Method 2: Manual Installation

If you prefer manual control:

**Step 1**: Download the compose file
```bash
curl -fsSL https://raw.githubusercontent.com/joachimbrindeau/claude-proxy-multi/main/docker/compose.dist.yaml \
  -o docker-compose.yml
```

**Step 2**: Create data directory
```bash
mkdir -p ./data
chmod 700 ./data
```

**Step 3**: Start services
```bash
docker-compose up -d
```

**Step 4**: Verify health
```bash
curl http://localhost:8000/health
```

**Step 5**: Open web UI
```
http://localhost:8000/accounts
```

---

## Configuration

The Docker image uses these default settings:

| Setting | Default | Description |
|---------|---------|-------------|
| **Port** | 8000 | HTTP server port |
| **Host** | 0.0.0.0 | Listen on all interfaces |
| **Log Level** | INFO | Logging verbosity |
| **Accounts Path** | /config/accounts.json | OAuth credentials storage |
| **Rotation** | Enabled | Automatic account rotation |
| **Hot Reload** | Enabled | Live account updates |

### Custom Configuration

Override environment variables in `docker-compose.yml`:

```yaml
services:
  claude-code-proxy:
    environment:
      - SERVER__PORT=9000  # Change port
      - SERVER__LOG_LEVEL=DEBUG  # More verbose logs
      - CCPROXY_ROTATION_ENABLED=false  # Disable rotation
```

Then restart:
```bash
docker-compose restart
```

### Data Persistence

OAuth credentials are stored in a Docker volume:
```yaml
volumes:
  - claude-code-proxy-config:/config
```

**Backup accounts**:
```bash
# Export from web UI
curl http://localhost:8000/api/accounts > accounts-backup.json

# Or copy from volume
docker cp claude-code-proxy:/config/accounts.json ./accounts-backup.json
```

**Restore accounts**:
```bash
# Import via web UI at http://localhost:8000/accounts
# Or manually:
docker cp ./accounts-backup.json claude-code-proxy:/config/accounts.json
docker-compose restart
```

---

## Adding Claude Accounts

After installation, add your Claude accounts via OAuth:

1. **Open the web UI**:
   ```
   http://localhost:8000/accounts
   ```

2. **Click "Add Account"**

3. **Copy the OAuth URL** and open it in your browser

4. **Sign in** with your Claude account

5. **Copy the authorization code** from the page

6. **Paste the code** back into the web UI

7. **Done!** Your account is now active

Repeat for additional accounts. The proxy will automatically rotate between them.

---

## Usage

### Proxy API (Anthropic-Compatible)

Use the standard Anthropic SDK with the proxy endpoint:

**Python**:
```python
from anthropic import Anthropic

client = Anthropic(
    base_url="http://localhost:8000/api",
    api_key="any-value"  # Ignored, using OAuth
)

response = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=1024,
    messages=[{"role": "user", "content": "Hello!"}]
)
```

**JavaScript/TypeScript**:
```typescript
import Anthropic from '@anthropic-ai/sdk';

const client = new Anthropic({
  baseURL: 'http://localhost:8000/api',
  apiKey: 'any-value'  // Ignored, using OAuth
});

const response = await client.messages.create({
  model: 'claude-sonnet-4-20250514',
  max_tokens: 1024,
  messages: [{ role: 'user', content: 'Hello!' }]
});
```

**curl**:
```bash
curl http://localhost:8000/api/v1/messages \
  -H "Content-Type: application/json" \
  -H "x-api-key: any-value" \
  -d '{
    "model": "claude-sonnet-4-20250514",
    "max_tokens": 1024,
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

### SDK Endpoints

Direct Claude SDK endpoints (bypass Anthropic SDK):

```bash
# Messages endpoint
POST http://localhost:8000/sdk/v1/messages

# Models list
GET http://localhost:8000/sdk/v1/models
```

---

## Management Commands

### View Logs
```bash
docker-compose logs -f
```

### Stop Service
```bash
docker-compose down
```

### Restart Service
```bash
docker-compose restart
```

### Update to Latest
```bash
docker-compose pull
docker-compose up -d
```

### Check Status
```bash
docker-compose ps
```

### Remove Everything
```bash
# Stop and remove containers
docker-compose down

# Remove volumes (⚠️ deletes accounts!)
docker-compose down -v
```

---

## Troubleshooting

### Port Already in Use

**Problem**: `bind: address already in use`

**Solution**: Change the port in `docker-compose.yml`:
```yaml
ports:
  - '9000:8000'  # Use port 9000 instead
```

### Health Check Failing

**Problem**: Service won't start, health check times out

**Solutions**:
1. Check logs: `docker-compose logs`
2. Verify Docker has enough resources (Settings → Resources)
3. Try manual health check: `curl http://localhost:8000/health`

### Cannot Access Web UI

**Problem**: `http://localhost:8000/accounts` not loading

**Solutions**:
1. Verify service is running: `docker-compose ps`
2. Check firewall allows port 8000
3. Try http://127.0.0.1:8000/accounts
4. Check browser console for errors

### OAuth Flow Issues

**Problem**: Can't add accounts via OAuth

**Solutions**:
1. Ensure you're using a valid Claude account
2. Check if you're already logged into Claude in the same browser
3. Try incognito/private browsing mode
4. Verify the OAuth URL is copied completely

### Docker Daemon Not Running

**Problem**: `Cannot connect to the Docker daemon`

**Solutions**:
- **macOS**: Start Docker Desktop
- **Windows**: Start Docker Desktop
- **Linux**: `sudo systemctl start docker`

---

## Advanced Topics

### Using with VSCode

Set the proxy as your Anthropic API endpoint:

**settings.json**:
```json
{
  "anthropic.baseURL": "http://localhost:8000/api"
}
```

### Reverse Proxy (nginx)

Expose the proxy securely:

```nginx
server {
    listen 443 ssl;
    server_name claude.example.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### Custom Network

Integrate with other Docker services:

```yaml
services:
  claude-code-proxy:
    networks:
      - my-network

networks:
  my-network:
    external: true
```

---

## Migration

### From Another Installation

Export accounts from old installation:
```bash
curl http://old-server:8000/api/accounts > accounts.json
```

Import to new Docker installation:
```bash
# Via web UI at http://localhost:8000/accounts
# Or use API:
curl -X POST http://localhost:8000/api/accounts/import \
  -H "Content-Type: application/json" \
  -d @accounts.json
```

### To Another Method (Homebrew, etc.)

Docker → Homebrew:
```bash
# Export from Docker
curl http://localhost:8000/api/accounts > accounts.json

# Stop Docker instance
docker-compose down

# Install via Homebrew
brew install joachimbrindeau/claude-code-proxy/claude-code-proxy

# Import accounts via web UI at http://localhost:8080/accounts
```

---

## Uninstallation

### Remove Service Only
```bash
docker-compose down
rm docker-compose.yml
```

### Remove Everything (including accounts)
```bash
docker-compose down -v
rm docker-compose.yml
rm -rf ./data
```

---

## Next Steps

- 📖 [API Documentation](../api/README.md)
- 🔧 [Configuration Guide](../configuration/README.md)
- 🚀 [Advanced Usage](../advanced/README.md)
- 💬 [Get Help](https://github.com/joachimbrindeau/claude-proxy-multi/issues)
