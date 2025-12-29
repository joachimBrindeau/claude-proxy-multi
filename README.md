<div align="center">

# CCProxy Multi-Account

**Claude Code Proxy with Multi-Account Rotation & Rate Limit Failover**

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Claude API](https://img.shields.io/badge/Claude-API-orange.svg)](https://www.anthropic.com/)

---

### Fork of [CaddyGlow/ccproxy-api](https://github.com/CaddyGlow/ccproxy-api)

This project is built on top of the excellent **CCProxy** by [@CaddyGlow](https://github.com/CaddyGlow).
All core proxy functionality, authentication, and API translation comes from the original project.

**This fork adds:** Multi-account rotation with automatic failover

---

[Features](#-features) · [Quick Start](#-quick-start) · [Multi-Account Setup](#-multi-account-rotation) · [API Reference](#-api-endpoints) · [Configuration](#-configuration)

</div>

---

## What This Fork Adds

Built on top of CaddyGlow's CCProxy, this fork adds **multi-account rotation** for production deployments:

- **3x+ throughput** by distributing requests across multiple Claude accounts
- **Zero downtime** with automatic failover when accounts hit rate limits
- **Hands-off operation** with proactive token refresh before expiration
- **Live updates** via hot-reload - add/remove accounts without restart

| Feature | Source |
|---------|:------:|
| Claude API proxy | [Original](https://github.com/CaddyGlow/ccproxy-api) |
| OAuth2 authentication | [Original](https://github.com/CaddyGlow/ccproxy-api) |
| SDK & API modes | [Original](https://github.com/CaddyGlow/ccproxy-api) |
| OpenAI format compatibility | [Original](https://github.com/CaddyGlow/ccproxy-api) |
| Observability suite | [Original](https://github.com/CaddyGlow/ccproxy-api) |
| **Multi-account rotation** | This Fork |
| **Rate limit failover** | This Fork |
| **Proactive token refresh** | This Fork |
| **Hot-reload accounts** | This Fork |
| **Account status API** | This Fork |

---

## ✨ Features

### Core Proxy Features (Inherited)

<details>
<summary><b>🔌 Claude API Support</b></summary>

- **Anthropic Claude** - Access via Claude Max subscription
- **OpenAI Format** - Accepts requests in OpenAI chat completions format
- **Format Translation** - Automatic conversion from OpenAI to Anthropic format

</details>

<details>
<summary><b>🛠️ Dual Operating Modes</b></summary>

| Mode | Endpoint | Description |
|------|----------|-------------|
| **SDK** | `/sdk/v1/*` | Routes through `claude-code-sdk` with MCP tools |
| **API** | `/api/v1/*` | Direct proxy with auth header injection |

</details>

<details>
<summary><b>🔐 Authentication Options</b></summary>

- OAuth2 PKCE flow for Claude
- Automatic credential detection from CLI tools
- Token refresh with configurable buffer time
- Multiple header formats (`x-api-key`, `Authorization: Bearer`)

</details>

<details>
<summary><b>📊 Observability Suite</b></summary>

- Prometheus metrics at `/metrics`
- DuckDB access logs with cost tracking
- Real-time dashboard at `/dashboard`
- Query API for historical analytics

</details>

### Multi-Account Features (This Fork)

<details open>
<summary><b>🔄 Intelligent Rotation</b></summary>

- **Round-Robin Distribution** - Evenly spreads load across all accounts
- **Rate Limit Detection** - Automatically detects HTTP 429 responses
- **Instant Failover** - Retries with next available account in <100ms
- **Cooldown Tracking** - Respects `retry-after` headers per account

</details>

<details open>
<summary><b>🔑 Token Lifecycle Management</b></summary>

- **Proactive Refresh** - Renews tokens 10 minutes before expiration
- **Background Scheduler** - APScheduler-based refresh without request blocking
- **Failure Isolation** - Auth errors don't affect other accounts
- **Manual Override** - Force refresh via API endpoint

</details>

<details open>
<summary><b>📡 Real-Time Monitoring</b></summary>

```bash
# Aggregate pool status
curl http://localhost:8000/status

# Per-account details
curl http://localhost:8000/status/accounts

# Response:
{
  "totalAccounts": 3,
  "availableAccounts": 3,
  "rateLimitedAccounts": 0,
  "nextAccount": "account-1",
  "accounts": [...]
}
```

</details>

<details open>
<summary><b>⚡ Zero-Downtime Operations</b></summary>

- **Hot Reload** - File watcher detects `accounts.json` changes
- **Graceful Updates** - New accounts added without restart
- **State Preservation** - Rotation index maintained across reloads

</details>

---

## 🚀 Quick Start

### Installation

```bash
# Install with uv (recommended)
uv tool install git+https://github.com/joachimBrindeau/ccproxy-api.git

# Or with pipx
pipx install git+https://github.com/joachimBrindeau/ccproxy-api.git

# Required: Claude Code CLI for SDK mode
npm install -g @anthropic-ai/claude-code
```

### Single Account (Simple)

```bash
# Login with Claude CLI
claude /login

# Start proxy
ccproxy
```

### Multi-Account (Production)

```bash
# 1. Create accounts file
cat > ~/.claude/accounts.json << 'EOF'
{
  "version": 1,
  "accounts": {
    "primary": {
      "accessToken": "sk-ant-oat01-...",
      "refreshToken": "sk-ant-ort01-...",
      "expiresAt": 1747909518727
    },
    "secondary": {
      "accessToken": "sk-ant-oat01-...",
      "refreshToken": "sk-ant-ort01-...",
      "expiresAt": 1747909518727
    }
  }
}
EOF

# 2. Start proxy with rotation
ccproxy

# 3. Verify accounts loaded
curl http://localhost:8000/status
```

---

## 🔄 Multi-Account Rotation

### How It Works

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│   Client    │────▶│   CCProxy    │────▶│  Claude API     │
│   Request   │     │  (Rotation)  │     │                 │
└─────────────┘     └──────────────┘     └─────────────────┘
                           │
                    ┌──────┴──────┐
                    ▼             ▼
              ┌─────────┐   ┌─────────┐
              │Account 1│   │Account 2│  ...
              │Available│   │Available│
              └─────────┘   └─────────┘
```

1. Request arrives at proxy
2. Rotation pool selects next available account
3. Request forwarded with account's auth token
4. On success: response returned, rotation advances
5. On 429: automatic retry with next account

### Account States

| State | Description | Auto-Recovery |
|-------|-------------|:-------------:|
| `available` | Ready for requests | - |
| `rate_limited` | Hit 429, in cooldown | ✅ After cooldown |
| `auth_error` | Token invalid/expired | ✅ Via refresh |
| `disabled` | Manually disabled | Manual only |

### Configuration

**Environment Variables:**

| Variable | Default | Description |
|----------|---------|-------------|
| `CCPROXY_ACCOUNTS_PATH` | `~/.claude/accounts.json` | Accounts file location |
| `CCPROXY_ROTATION_ENABLED` | `true` | Enable/disable rotation |
| `CCPROXY_HOT_RELOAD` | `true` | Watch file for changes |
| `CCPROXY_REFRESH_BUFFER` | `600` | Seconds before expiry to refresh |

**Manual Account Selection:**

```bash
# Bypass rotation, use specific account
curl -X POST http://localhost:8000/api/v1/messages \
  -H "X-Account-Name: primary" \
  -H "Content-Type: application/json" \
  -d '{"model": "claude-sonnet-4-20250514", "messages": [...]}'
```

### Status API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/status` | GET | Pool aggregate status |
| `/status/accounts` | GET | All accounts list |
| `/status/accounts/{name}` | GET | Single account details |
| `/status/accounts/{name}/refresh` | POST | Force token refresh |
| `/status/accounts/{name}/enable` | POST | Re-enable disabled account |

---

## 📡 API Endpoints

### Claude Endpoints

| Endpoint | Format | Mode |
|----------|--------|------|
| `POST /api/v1/messages` | Anthropic | Direct Proxy |
| `POST /api/v1/chat/completions` | OpenAI | Direct Proxy |
| `POST /sdk/v1/messages` | Anthropic | SDK with Tools |
| `POST /sdk/v1/chat/completions` | OpenAI | SDK with Tools |
| `GET /api/v1/models` | - | List Models |

### Utility Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /health` | Health check with account info |
| `GET /status` | Rotation pool status |
| `GET /metrics` | Prometheus metrics |
| `GET /dashboard` | Web UI dashboard |

---

## ⚙️ Configuration

### Precedence Order

1. Command-line arguments
2. Environment variables
3. `.env` file
4. TOML config (`~/.config/ccproxy/config.toml`)
5. Defaults

### Example Configuration

```toml
# ~/.config/ccproxy/config.toml

[server]
host = "0.0.0.0"
port = 8000

[rotation]
enabled = true
accounts_path = "~/.claude/accounts.json"
hot_reload = true
refresh_buffer_seconds = 600

[security]
auth_token = "your-secret-token"
```

### Docker Deployment

```yaml
# docker-compose.yml
services:
  ccproxy:
    image: ghcr.io/joachimbrindeau/ccproxy-api:latest
    ports:
      - "8000:8000"
    volumes:
      - ./accounts.json:/config/accounts.json:ro
    environment:
      - CCPROXY_ACCOUNTS_PATH=/config/accounts.json
```

---

## 🔧 Client Configuration

### Environment Variables

```bash
# For Anthropic-compatible clients
export ANTHROPIC_BASE_URL="http://localhost:8000/api"
export ANTHROPIC_API_KEY="dummy"

# For OpenAI-compatible clients
export OPENAI_BASE_URL="http://localhost:8000/api/v1"
export OPENAI_API_KEY="dummy"
```

### Popular Tools

<details>
<summary><b>Aider</b></summary>

```bash
export ANTHROPIC_API_KEY=dummy
export ANTHROPIC_BASE_URL=http://localhost:8000/api
aider --model claude-sonnet-4-20250514
```

</details>

<details>
<summary><b>LiteLLM</b></summary>

```yaml
# litellm_config.yaml
model_list:
  - model_name: claude-sonnet
    litellm_params:
      model: anthropic/claude-sonnet-4-20250514
      api_base: http://localhost:8000/api
      api_key: dummy
```

</details>

<details>
<summary><b>Continue.dev</b></summary>

```json
{
  "models": [{
    "provider": "anthropic",
    "model": "claude-sonnet-4-20250514",
    "apiBase": "http://localhost:8000/api",
    "apiKey": "dummy"
  }]
}
```

</details>

---

## 📊 Supported Models

| Model | ID |
|-------|-----|
| Claude Opus 4 | `claude-opus-4-20250514` |
| Claude Sonnet 4 | `claude-sonnet-4-20250514` |
| Claude 3.7 Sonnet | `claude-3-7-sonnet-20250219` |
| Claude 3.5 Sonnet | `claude-3-5-sonnet-20241022` |
| Claude 3.5 Haiku | `claude-3-5-haiku-20241022` |

---

## 🐛 Troubleshooting

<details>
<summary><b>Authentication Errors</b></summary>

```bash
# Check credential status
ccproxy auth status

# Re-authenticate
ccproxy auth login
```

</details>

<details>
<summary><b>All Accounts Rate Limited</b></summary>

```bash
# Check account states
curl http://localhost:8000/status

# Wait for cooldown or add more accounts to rotation
```

</details>

<details>
<summary><b>Token Refresh Failing</b></summary>

```bash
# Force manual refresh
curl -X POST http://localhost:8000/status/accounts/{name}/refresh

# Check logs for OAuth errors
docker logs ccproxy 2>&1 | grep -i oauth
```

</details>

---

## 🤝 Contributing

Contributions welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md).

## 📄 License

MIT License - see [LICENSE](LICENSE).

## 🙏 Acknowledgments

### Original Project

This fork would not exist without the excellent work by **[@CaddyGlow](https://github.com/CaddyGlow)** on [ccproxy-api](https://github.com/CaddyGlow/ccproxy-api).

The original CCProxy provides:
- Claude proxy architecture with OpenAI format compatibility
- OAuth2 PKCE authentication flows
- SDK and API operating modes
- MCP server integration
- Observability suite (metrics, dashboard, logging)

**If you don't need multi-account rotation, use the [original project](https://github.com/CaddyGlow/ccproxy-api).**

### Also Thanks To

- [Anthropic](https://anthropic.com) - Claude API & SDK

---

<div align="center">

**[⬆ Back to Top](#ccproxy-multi-account)**

</div>
