# Multi-Account Rotation

CCProxy supports rotating between multiple Claude Pro/Max accounts to distribute usage and handle rate limits automatically.

## Quick Start

1. **Create an accounts file** at `~/.claude/accounts.json`:

```json
{
  "version": 1,
  "accounts": {
    "primary": {
      "accessToken": "sk-ant-oat01-YOUR_ACCESS_TOKEN",
      "refreshToken": "sk-ant-ort01-YOUR_REFRESH_TOKEN",
      "expiresAt": 1734567890123
    },
    "secondary": {
      "accessToken": "sk-ant-oat01-ANOTHER_ACCESS_TOKEN",
      "refreshToken": "sk-ant-ort01-ANOTHER_REFRESH_TOKEN",
      "expiresAt": 1734567890123
    }
  }
}
```

2. **Start the server** - rotation is enabled automatically when accounts.json exists:

```bash
ccproxy serve
```

## Features

### Automatic Round-Robin Rotation
Requests are distributed across accounts using round-robin selection. Each request gets the next available account.

### Rate Limit Detection & Failover
When an account hits a rate limit (HTTP 429):
1. The account is marked as rate-limited
2. Request is automatically retried with the next available account
3. Up to 3 retry attempts per request
4. Rate-limited accounts are restored when their cooldown expires

### Proactive Token Refresh
- Tokens are refreshed automatically 10 minutes before expiration
- Exponential backoff retry on refresh failures
- Accounts marked as `auth_error` when refresh tokens expire

### Hot-Reload
- Changes to `accounts.json` are detected automatically
- Accounts are reloaded without server restart
- Add or remove accounts while the server is running

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CCPROXY_ACCOUNTS_PATH` | `~/.claude/accounts.json` | Path to accounts file |
| `CCPROXY_ROTATION_ENABLED` | `true` | Enable/disable rotation |
| `CCPROXY_HOT_RELOAD` | `true` | Enable/disable file watching |

### Accounts File Format

```json
{
  "version": 1,
  "accounts": {
    "<account-name>": {
      "accessToken": "sk-ant-oat01-...",
      "refreshToken": "sk-ant-ort01-...",
      "expiresAt": <unix-timestamp-ms>
    }
  }
}
```

- **account-name**: Lowercase alphanumeric with underscores/hyphens (max 32 chars)
- **accessToken**: Claude OAuth access token (starts with `sk-ant-oat01-`)
- **refreshToken**: Claude OAuth refresh token (starts with `sk-ant-ort01-`)
- **expiresAt**: Token expiration timestamp in milliseconds

### Getting Tokens

You can get tokens from the Claude CLI credentials file:

```bash
# View your current credentials
cat ~/.claude/credentials.json

# Copy the accessToken, refreshToken, and expiresAt values
```

## API Endpoints

### GET /status

Get rotation pool status:

```bash
curl http://localhost:8080/status
```

Response:
```json
{
  "totalAccounts": 2,
  "availableAccounts": 2,
  "rateLimitedAccounts": 0,
  "authErrorAccounts": 0,
  "nextAccount": "primary",
  "accounts": [
    {
      "name": "primary",
      "state": "available",
      "tokenExpiresAt": "2024-12-20T10:00:00Z",
      "tokenExpiresIn": 3600,
      "rateLimitedUntil": null,
      "lastUsed": "2024-12-19T15:30:00Z",
      "lastError": null
    }
  ]
}
```

### GET /status/accounts/{name}

Get status for a specific account:

```bash
curl http://localhost:8080/status/accounts/primary
```

### POST /status/accounts/{name}/refresh

Force token refresh for an account:

```bash
curl -X POST http://localhost:8080/status/accounts/primary/refresh
```

### POST /status/accounts/{name}/enable

Re-enable an account (clear rate limit or auth error):

```bash
curl -X POST http://localhost:8080/status/accounts/primary/enable
```

## Manual Account Selection

Use the `X-Account-Name` header to select a specific account:

```bash
curl -H "X-Account-Name: primary" \
     -H "Content-Type: application/json" \
     -d '{"model": "claude-3-5-sonnet-20241022", "messages": [{"role": "user", "content": "Hello"}]}' \
     http://localhost:8080/api/v1/chat/completions
```

Notes:
- Manual selection bypasses round-robin rotation
- Rate limits are still tracked
- No automatic retry on rate limit with manual selection

## Account States

| State | Description | Recovery |
|-------|-------------|----------|
| `available` | Ready for requests | N/A |
| `rate_limited` | Hit rate limit | Auto-recovers after cooldown |
| `auth_error` | Authentication failed | Manual re-auth required |
| `disabled` | Manually disabled | Enable via API |

## Systemd Service

For production deployments, use the systemd service template:

```bash
# Copy the template
cp systemd/ccproxy-rotation.service.template /etc/systemd/user/ccproxy.service

# Edit the template with your paths
# Replace {{WORKING_DIR}}, {{UV_PATH}}, {{ACCOUNTS_PATH}}, etc.

# Enable and start
systemctl --user daemon-reload
systemctl --user enable ccproxy
systemctl --user start ccproxy

# View logs
journalctl --user -u ccproxy -f
```

## Troubleshooting

### "No accounts available"
- Check that accounts.json exists and has valid accounts
- Verify tokens haven't expired
- Check `/status` to see account states

### "Account auth_error"
- Refresh token has expired
- Re-authenticate with Claude CLI and update accounts.json

### Hot-reload not working
- Ensure `CCPROXY_HOT_RELOAD` is not set to `false`
- Check file permissions on accounts.json
- View logs for file watcher errors

### Rate limits still occurring
- Consider adding more accounts
- Check if all accounts are rate-limited simultaneously
- Use `/status` to monitor cooldown times
