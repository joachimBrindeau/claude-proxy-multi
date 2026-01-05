# Homebrew Installation Guide

Install Claude Code Proxy using Homebrew for native macOS integration with automatic updates.

## Quick Start

**Install with Homebrew**:
```bash
brew install joachimbrindeau/claude-code-proxy/claude-code-proxy
```

**Start the service**:
```bash
brew services start claude-code-proxy
```

**Open web UI**:
```
http://localhost:8080/accounts
```

**Installation time**: ~2 minutes ⚡

---

## Prerequisites

### Required

- **macOS** 11.0 (Big Sur) or later, OR
- **Linux** with [Homebrew on Linux](https://docs.brew.sh/Homebrew-on-Linux) installed
- **Homebrew** 4.0.0+ ([Install Homebrew](https://brew.sh/))

### Optional

- **Python** 3.12+ (automatically installed as dependency)

---

## Installation

### Step 1: Tap the Repository

Add the Claude Code Proxy tap:

```bash
brew tap joachimbrindeau/claude-code-proxy
```

This connects Homebrew to the formula repository.

### Step 2: Install the Formula

```bash
brew install claude-code-proxy
```

This will:
- Install Python 3.12 (if not already installed)
- Create a virtualenv at `/opt/homebrew/Cellar/claude-code-proxy/<version>/`
- Install all Python dependencies
- Create service configuration
- Set up log directories

### Step 3: Start the Service

```bash
brew services start claude-code-proxy
```

The service will:
- Start automatically on boot
- Run at `http://localhost:8080`
- Log to `/opt/homebrew/var/log/claude-code-proxy/`

### Step 4: Verify Installation

Check service status:
```bash
brew services list | grep claude-code-proxy
```

Check health endpoint:
```bash
curl http://localhost:8080/health
```

View logs:
```bash
tail -f /opt/homebrew/var/log/claude-code-proxy/stdout.log
```

---

## Adding Claude Accounts

After installation, configure your Claude accounts:

1. **Open the web UI**:
   ```
   http://localhost:8080/accounts
   ```

2. **Add accounts via OAuth** (same process as Docker installation)

3. **Accounts persist** across restarts in:
   ```
   /opt/homebrew/var/claude-code-proxy/data/accounts.json
   ```

---

## Usage

### Proxy API

Use with the Anthropic SDK:

**Python**:
```python
from anthropic import Anthropic

client = Anthropic(
    base_url="http://localhost:8080/api",
    api_key="any-value"  # Ignored, using OAuth
)

response = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=1024,
    messages=[{"role": "user", "content": "Hello from Homebrew!"}]
)
```

**TypeScript**:
```typescript
import Anthropic from '@anthropic-ai/sdk';

const client = new Anthropic({
  baseURL: 'http://localhost:8080/api',
  apiKey: 'any-value'
});
```

### SDK Endpoints

Direct endpoints (bypass Anthropic SDK):

```bash
# Messages
POST http://localhost:8080/sdk/v1/messages

# Models
GET http://localhost:8080/sdk/v1/models
```

---

## Service Management

### Start Service
```bash
brew services start claude-code-proxy
```

### Stop Service
```bash
brew services stop claude-code-proxy
```

### Restart Service
```bash
brew services restart claude-code-proxy
```

### Check Status
```bash
brew services info claude-code-proxy
```

### Run Without Service (Foreground)
```bash
claude-code-proxy-api --host 0.0.0.0 --port 8080
```

---

## Configuration

### Change Port

Edit the service plist:
```bash
# Find plist location
brew services list | grep claude-code-proxy

# Edit (macOS)
vim ~/Library/LaunchAgents/homebrew.mxcl.claude-code-proxy.plist

# Change port in ProgramArguments
<string>--port</string>
<string>9000</string>

# Reload
brew services restart claude-code-proxy
```

### Change Log Level

Set environment variable:
```bash
# Edit plist
vim ~/Library/LaunchAgents/homebrew.mxcl.claude-code-proxy.plist

# Add under ProgramArguments
<key>EnvironmentVariables</key>
<dict>
  <key>SERVER__LOG_LEVEL</key>
  <string>DEBUG</string>
</dict>

# Reload
brew services restart claude-code-proxy
```

### Data Directory

Default location:
```
/opt/homebrew/var/claude-code-proxy/data/
```

Accounts file:
```
/opt/homebrew/var/claude-code-proxy/data/accounts.json
```

---

## Updating

### Update to Latest Version

```bash
brew update
brew upgrade claude-code-proxy
brew services restart claude-code-proxy
```

### Check for Updates

```bash
brew outdated | grep claude-code-proxy
```

### Pin Version (Prevent Updates)

```bash
brew pin claude-code-proxy
```

### Unpin Version

```bash
brew unpin claude-code-proxy
```

---

## Logs and Debugging

### View Logs

**Standard output**:
```bash
tail -f /opt/homebrew/var/log/claude-code-proxy/stdout.log
```

**Error output**:
```bash
tail -f /opt/homebrew/var/log/claude-code-proxy/stderr.log
```

**Combined**:
```bash
tail -f /opt/homebrew/var/log/claude-code-proxy/*.log
```

### Debug Mode

Run manually with debug logging:
```bash
# Stop service first
brew services stop claude-code-proxy

# Run with debug
SERVER__LOG_LEVEL=DEBUG claude-code-proxy-api --host 0.0.0.0 --port 8080
```

---

## Backup and Restore

### Backup Accounts

**Via API**:
```bash
curl http://localhost:8080/api/accounts > ~/claude-code-proxy-backup.json
```

**Direct file copy**:
```bash
cp /opt/homebrew/var/claude-code-proxy/data/accounts.json ~/claude-code-proxy-backup.json
```

### Restore Accounts

**Via web UI**:
1. Open http://localhost:8080/accounts
2. Click "Import Accounts"
3. Select backup file

**Direct file copy**:
```bash
cp ~/claude-code-proxy-backup.json /opt/homebrew/var/claude-code-proxy/data/accounts.json
brew services restart claude-code-proxy
```

---

## Troubleshooting

### Port Already in Use

**Problem**: `Address already in use`

**Solution**: Change port (see Configuration section) or stop conflicting service:
```bash
lsof -ti:8080 | xargs kill
```

### Service Won't Start

**Problem**: `brew services start` fails

**Solutions**:
1. Check logs:
   ```bash
   tail -f /opt/homebrew/var/log/claude-code-proxy/stderr.log
   ```

2. Verify Python installation:
   ```bash
   brew info python@3.12
   ```

3. Reinstall formula:
   ```bash
   brew reinstall claude-code-proxy
   ```

4. Check permissions:
   ```bash
   ls -la /opt/homebrew/var/claude-code-proxy/
   ```

### Formula Installation Fails

**Problem**: `Error: Failed to download resource`

**Solutions**:
1. Update Homebrew:
   ```bash
   brew update
   ```

2. Check internet connection

3. Retry with verbose output:
   ```bash
   brew install --verbose claude-code-proxy
   ```

### Cannot Access Web UI

**Problem**: `http://localhost:8080` not loading

**Solutions**:
1. Verify service is running:
   ```bash
   brew services list | grep claude-code-proxy
   ```

2. Check if port is accessible:
   ```bash
   curl http://localhost:8080/health
   ```

3. Check firewall settings (macOS):
   ```bash
   System Preferences → Security & Privacy → Firewall
   ```

### Python Import Errors

**Problem**: `ModuleNotFoundError` in logs

**Solutions**:
1. Reinstall formula:
   ```bash
   brew reinstall claude-code-proxy
   ```

2. Clear Homebrew cache:
   ```bash
   rm -rf $(brew --cache)/claude-code-proxy*
   brew install claude-code-proxy
   ```

---

## Migration

### From Docker to Homebrew

**Step 1**: Export accounts from Docker
```bash
curl http://localhost:8000/api/accounts > accounts.json
```

**Step 2**: Stop Docker
```bash
docker-compose down
```

**Step 3**: Install Homebrew version
```bash
brew install joachimbrindeau/claude-code-proxy/claude-code-proxy
brew services start claude-code-proxy
```

**Step 4**: Import accounts
- Open http://localhost:8080/accounts
- Click "Import Accounts"
- Select `accounts.json`

### From Homebrew to Another Method

Export accounts before uninstalling:
```bash
curl http://localhost:8080/api/accounts > ~/claude-code-proxy-backup.json
```

---

## Uninstallation

### Remove Formula Only

```bash
brew services stop claude-code-proxy
brew uninstall claude-code-proxy
```

Data remains at `/opt/homebrew/var/claude-code-proxy/`

### Complete Removal (Including Data)

```bash
brew services stop claude-code-proxy
brew uninstall claude-code-proxy
rm -rf /opt/homebrew/var/claude-code-proxy/
rm -rf /opt/homebrew/var/log/claude-code-proxy/
```

### Untap Repository

```bash
brew untap joachimbrindeau/claude-code-proxy
```

---

## Advanced Topics

### Using with VSCode

Configure VSCode to use the Homebrew proxy:

**settings.json**:
```json
{
  "anthropic.baseURL": "http://localhost:8080/api"
}
```

### System-Wide Service (All Users)

```bash
# Install as system service
sudo brew services start claude-code-proxy

# Service runs for all users
# Requires admin privileges
```

### Custom Installation Location

Homebrew installs to:
- **Apple Silicon**: `/opt/homebrew/`
- **Intel**: `/usr/local/`

Cannot be changed per Homebrew design.

### Multiple Versions

```bash
# Install specific version
brew install joachimbrindeau/claude-code-proxy/claude-code-proxy@0.1.0

# Switch versions
brew switch claude-code-proxy 0.1.0
brew switch claude-code-proxy 0.2.0
```

---

## Comparison with Other Methods

| Feature | Homebrew | Docker | Manual |
|---------|----------|--------|--------|
| **Installation** | 2 min | 1 min | 5 min |
| **Auto-start** | ✅ Native | ✅ Docker | ❌ Manual |
| **Updates** | `brew upgrade` | `docker pull` | Manual |
| **System Integration** | ✅ Native | ⚠️ Container | ✅ Native |
| **Resource Usage** | Low | Medium | Low |
| **Best For** | macOS users | Cross-platform | Developers |

---

## Next Steps

- 📖 [API Documentation](../api/README.md)
- 🔧 [Configuration Guide](../configuration/README.md)
- 🐳 [Docker Installation](./docker.md)
- 💬 [Get Help](https://github.com/joachimbrindeau/claude-proxy-multi/issues)
