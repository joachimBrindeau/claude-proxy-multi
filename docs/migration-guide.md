# Migration Guide: ccproxy to ccproxy-multi

This guide helps you migrate from the original ccproxy to ccproxy-multi with multi-account rotation support.

## Overview

ccproxy-multi is a fork of ccproxy-api that adds:
- Multi-account support with round-robin rotation
- Automatic rate limit failover
- Proactive token refresh
- Status monitoring endpoints
- Manual account selection via headers

All existing ccproxy features are preserved.

## Prerequisites

- Running ccproxy installation
- Python 3.11+
- At least one Claude account with OAuth tokens
- (Optional) Additional Claude accounts for rotation

## Migration Steps

### Step 1: Backup Current Configuration

```bash
# Backup current credentials
cp ~/.claude/.credentials.json ~/.claude/.credentials.json.backup

# Note your current LiteLLM configuration
cat /path/to/litellm/config.yaml | grep -A5 "ccproxy"
```

### Step 2: Prepare accounts.json

Create `~/.claude/accounts.json` from your existing credentials:

```bash
# Extract tokens from existing Claude Code credentials
cat ~/.claude/.credentials.json | python3 -c "
import json, sys
data = json.load(sys.stdin)
oauth = data.get('claudeAiOauth', {})
print(json.dumps({
    'version': 1,
    'accounts': {
        'primary': {
            'accessToken': oauth.get('accessToken', ''),
            'refreshToken': oauth.get('refreshToken', ''),
            'expiresAt': oauth.get('expiresAt', 0)
        }
    }
}, indent=2))
" > ~/.claude/accounts.json

# Secure the file
chmod 600 ~/.claude/accounts.json
```

### Step 3: Install ccproxy-multi

```bash
# Clone the fork
cd /opt  # or your preferred location
git clone https://github.com/your-org/ccproxy-multi.git
cd ccproxy-multi

# Install with uv (recommended)
uv sync

# Or with pip
pip install -e .
```

### Step 4: Test ccproxy-multi (Side-by-Side)

Run ccproxy-multi on a different port first:

```bash
# Start ccproxy-multi on port 8001
ccproxy serve --host 0.0.0.0 --port 8001

# Test health
curl http://localhost:8001/health

# Test rotation status (new endpoint)
curl http://localhost:8001/status

# Test chat completion
curl -X POST http://localhost:8001/api/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-sonnet-4-20250514",
    "messages": [{"role": "user", "content": "Hello"}]
  }'
```

### Step 5: Switch Over

Once verified, switch from ccproxy to ccproxy-multi:

```bash
# Stop original ccproxy
sudo systemctl stop ccproxy
sudo systemctl disable ccproxy

# Create systemd service for ccproxy-multi
sudo tee /etc/systemd/system/ccproxy-multi.service > /dev/null << 'EOF'
[Unit]
Description=CCProxy Multi-Account Rotation
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/opt/ccproxy-multi
ExecStart=/opt/ccproxy-multi/.venv/bin/ccproxy serve --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

Environment="CCPROXY_ACCOUNTS_PATH=/home/your-user/.claude/accounts.json"
Environment="CCPROXY_ROTATION_ENABLED=true"

[Install]
WantedBy=multi-user.target
EOF

# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable ccproxy-multi
sudo systemctl start ccproxy-multi

# Verify
curl http://localhost:8000/health
curl http://localhost:8000/status
```

### Step 6: Verify LiteLLM Integration

If using LiteLLM with ccproxy:

```bash
# From Docker network (typical LiteLLM setup)
curl -X POST http://172.17.0.1:8000/api/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-sonnet-4-20250514",
    "messages": [{"role": "user", "content": "Test"}]
  }'
```

No LiteLLM configuration changes required - ccproxy-multi uses the same endpoints.

## Post-Migration

### Add More Accounts (Optional)

To get the full benefit of rotation, add additional Claude accounts:

```bash
# Edit accounts.json
nano ~/.claude/accounts.json
```

Add accounts in this format:
```json
{
  "version": 1,
  "accounts": {
    "primary": { ... },
    "secondary": {
      "accessToken": "sk-ant-oat01-...",
      "refreshToken": "sk-ant-ort01-...",
      "expiresAt": 1747909518727
    }
  }
}
```

Changes are detected automatically (hot-reload within seconds).

### Monitor Account Status

```bash
# Check overall status
curl http://localhost:8000/status | jq

# Check specific account
curl http://localhost:8000/status/accounts/primary | jq
```

### View Rotation Logs

```bash
# Watch rotation events
sudo journalctl -u ccproxy-multi -f | grep -E "(rotation|account|rate_limit)"
```

## Rollback

If you need to rollback to original ccproxy:

```bash
# Stop ccproxy-multi
sudo systemctl stop ccproxy-multi
sudo systemctl disable ccproxy-multi

# Re-enable original ccproxy
sudo systemctl enable ccproxy
sudo systemctl start ccproxy
```

## Troubleshooting

### "Rotation pool not initialized"

The accounts.json file is missing or invalid:

```bash
# Check file exists and is valid JSON
cat ~/.claude/accounts.json | jq .

# Check file permissions
ls -la ~/.claude/accounts.json
# Should be -rw------- (600)
```

### "All accounts rate-limited"

All configured accounts have hit rate limits:

```bash
# Check when limits reset
curl http://localhost:8000/status | jq '.accounts[] | select(.state == "rate_limited") | {name, rateLimitedUntil}'
```

Options:
1. Wait for rate limits to reset
2. Add more accounts

### "Auth error" on account

The refresh token has expired:

```bash
# Re-authenticate the affected account
claude /login  # On a machine with that account

# Update tokens in accounts.json
```

### Service fails to start

```bash
# Check logs
sudo journalctl -u ccproxy-multi -n 100

# Common issues:
# - Port 8000 still in use by old ccproxy
# - Python environment not activated
# - Missing dependencies
```

## API Differences

| Endpoint | ccproxy | ccproxy-multi |
|----------|---------|---------------|
| Chat completions | `/api/v1/chat/completions` | Same |
| SDK mode | `/sdk/v1/messages` | Same |
| Health | `/health` | Same + rotation status |
| Status | N/A | `/status` |
| Account status | N/A | `/status/accounts` |
| Manual refresh | N/A | `POST /status/accounts/{name}/refresh` |

## Feature Comparison

| Feature | ccproxy | ccproxy-multi |
|---------|---------|---------------|
| OpenAI-compatible API | Yes | Yes |
| Anthropic format support | Yes | Yes |
| Streaming (SSE) | Yes | Yes |
| Connection pooling | Yes | Yes |
| Multi-account rotation | No | Yes |
| Rate limit failover | No | Yes |
| Token auto-refresh | No | Yes |
| Hot-reload config | No | Yes |
| Account status API | No | Yes |
