# CCProxy Configuration

This directory contains configuration files for the CCProxy Docker container.

## accounts.json (for multi-account rotation)

To enable multi-account rotation, create `accounts.json` with your Claude OAuth credentials:

```json
{
  "version": 1,
  "accounts": {
    "primary": {
      "accessToken": "sk-ant-oat01-...",
      "refreshToken": "sk-ant-ort01-...",
      "expiresAt": 1735689600000
    }
  }
}
```

**Token format:**
- `accessToken`: Starts with `sk-ant-oat01-`
- `refreshToken`: Starts with `sk-ant-ort01-`
- `expiresAt`: Unix timestamp in milliseconds

### Getting OAuth tokens

**Option 1: Use ccproxy auth login**
```bash
# Run without Docker first to authenticate
uv run ccproxy auth login

# Copy credentials to accounts.json format
# (tokens are saved to ~/.claude/.credentials.json)
```

**Option 2: Extract from Claude Code credentials**
Claude Code stores credentials in `~/.claude/.credentials.json`. Extract the OAuth token fields.

## Without accounts.json

If you don't create `accounts.json`, the proxy runs in single-account mode using your Claude Code credentials (from `~/.claude/.credentials.json` or keychain).
