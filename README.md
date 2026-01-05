<div align="center">

# Claude Code Proxy Multi-Account

**Claude Code Proxy with Multi-Account Rotation & Rate Limit Failover**

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Claude API](https://img.shields.io/badge/Claude-API-orange.svg)](https://www.anthropic.com/)

---

### Fork of [CaddyGlow/claude-code-proxy](https://github.com/CaddyGlow/claude-code-proxy)

This project is built on top of the excellent **Claude Code Proxy** by [@CaddyGlow](https://github.com/CaddyGlow).
All core proxy functionality, authentication, and API translation comes from the original project.

**This fork adds:** Multi-account rotation with automatic failover

---

[Features](#-features) · [Quick Start](#-quick-start) · [Multi-Account Setup](#-multi-account-rotation) · [API Reference](#-api-endpoints) · [Configuration](#-configuration)

</div>

---

## What This Fork Adds

Built on top of CaddyGlow's Claude Code Proxy, this fork adds **multi-account rotation** for production deployments:

- **3x+ throughput** by distributing requests across multiple Claude accounts
- **Zero downtime** with automatic failover when accounts hit rate limits
- **Hands-off operation** with proactive token refresh before expiration
- **Live updates** via hot-reload - add/remove accounts without restart

| Feature | Source |
|---------|:------:|
| Claude API proxy | [Original](https://github.com/CaddyGlow/claude-code-proxy) |
| OAuth2 authentication | [Original](https://github.com/CaddyGlow/claude-code-proxy) |
| SDK & API modes | [Original](https://github.com/CaddyGlow/claude-code-proxy) |
| OpenAI format compatibility | [Original](https://github.com/CaddyGlow/claude-code-proxy) |
| Observability suite | [Original](https://github.com/CaddyGlow/claude-code-proxy) |
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
uv tool install git+https://github.com/joachimBrindeau/claude-code-proxy.git

# Or with pipx
pipx install git+https://github.com/joachimBrindeau/claude-code-proxy.git

# Required: Claude Code CLI for SDK mode
npm install -g @anthropic-ai/claude-code
```

### Single Account (Simple)

```bash
# Login with Claude CLI
claude /login

# Start proxy
claude-code-proxy
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
claude-code-proxy

# 3. Verify accounts loaded
curl http://localhost:8000/status
```

### Cloud Deployment (One-Click)

Deploy to your preferred cloud platform with persistent storage:

[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/template/claude-code-proxy?referralCode=joachim)

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/joachimbrindeau/claude-proxy-multi)

**Fly.io**: `flyctl launch --config packaging/cloud/fly.toml`

> All cloud deployments include persistent storage for OAuth credentials and automatic account rotation.

---

## 📦 Installation Methods

Choose the installation method that fits your environment:

| Method | Best For | Install Time | Auto-Start | Commands |
|--------|----------|--------------|------------|----------|
| **[Docker](docs/installation/docker.md)** | Quick setup, cross-platform | ~60 seconds | ✅ Yes | `curl -fsSL https://joachimbrindeau.github.io/claude-proxy-multi/install.sh \| bash` |
| **[Homebrew](docs/installation/homebrew.md)** | macOS developers | ~2 minutes | ✅ Service | `brew install joachimbrindeau/claude-code-proxy/claude-code-proxy` |
| **[Cloud](docs/installation/cloud.md)** | Production deployments | ~3-5 minutes | ✅ Auto-scale | Click deploy button above |
| **[Windows](docs/installation/windows.md)** | Windows environments | ~3 minutes | ✅ Service | `choco install claude-code-proxy` |
| **[Linux/Snap](docs/installation/linux.md)** | Ubuntu/Debian servers | ~2 minutes | ✅ Daemon | `sudo snap install claude-code-proxy` |
| **[Kubernetes](docs/installation/kubernetes.md)** | Enterprise/K8s clusters | ~5 minutes | ✅ Deployment | `helm install claude-code-proxy/claude-code-proxy` |
| **[Binary](docs/installation/binaries.md)** | No dependencies needed | ~1 minute | ❌ Manual | Download from releases |

### Feature Comparison

| Feature | Docker | Homebrew | Cloud | Windows | Linux | Kubernetes | Binary |
|---------|--------|----------|-------|---------|-------|------------|--------|
| **Platform** | Any with Docker | macOS | Cloud | Windows 10+ | Ubuntu/Debian | Any K8s | Any |
| **Dependencies** | Docker only | None (managed) | None | None (managed) | None (managed) | Helm | None |
| **Persistence** | Volume | Filesystem | Volume | Registry | Filesystem | PVC | Filesystem |
| **Updates** | `docker pull` | `brew upgrade` | Auto/Git-based | `choco upgrade` | `snap refresh` | `helm upgrade` | Manual |
| **Resource Usage** | Medium | Low | Varies | Low | Low | Varies | Low |
| **Isolation** | Container | Native | Container | Native | Snap sandbox | Container | Native |
| **Multi-instance** | ✅ Easy | ⚠️ Manual | ✅ Auto-scale | ⚠️ Manual | ❌ Single | ✅ Replicas | ✅ Easy |
| **Production Ready** | ✅ Yes | ✅ Yes | ✅ Yes | ✅ Yes | ✅ Yes | ✅ Yes | ⚠️ Basic |

**Quick recommendations**:
- 🚀 **Quick testing**: Docker (60-second install)
- 🍎 **macOS development**: Homebrew (native integration)
- ☁️ **Production hosting**: Cloud platforms (auto-scaling)
- 🪟 **Windows workstations**: Chocolatey (service management)
- 🐧 **Linux servers**: Snap (automatic updates)
- ☸️ **Enterprise/DevOps**: Kubernetes (orchestration)
- 📦 **Air-gapped/offline**: Standalone binaries

---

## 🔄 Multi-Account Rotation

### How It Works

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│   Client    │────▶│   Claude Code Proxy    │────▶│  Claude API     │
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
4. TOML config (`~/.config/claude-code-proxy/config.toml`)
5. Defaults

### Example Configuration

```toml
# ~/.config/claude-code-proxy/config.toml

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

**Quick Start (Recommended):**

```bash
# One command to start
docker run -d -p 8000:8000 -v claude-code-proxy-config:/config \
  --name claude-code-proxy ghcr.io/joachimbrindeau/claude-proxy-multi:latest

# Open http://localhost:8000 to add accounts via web UI
```

**Docker Compose:**

```yaml
# docker/compose.yaml (or your own compose file)
services:
  claude-code-proxy:
    image: ghcr.io/joachimbrindeau/claude-proxy-multi:latest
    ports:
      - "8000:8000"
    volumes:
      - claude-code-proxy-config:/config
    environment:
      - CCPROXY_ACCOUNTS_PATH=/config/accounts.json
      - CCPROXY_ROTATION_ENABLED=true
      - CCPROXY_HOT_RELOAD=true

volumes:
  claude-code-proxy-config:
```

**First Run:**

1. Start the container
2. Visit `http://localhost:8000/` (redirects to setup if no accounts)
3. Click "Add Account" and complete OAuth flow
4. Credentials are saved to the volume, persisting across restarts

---

## API Key Authentication

For deployments exposed to the internet, enable per-user API keys:

### Enable API Keys

```bash
# Enable API key authentication
export CCPROXY_SECURITY_API_KEYS_ENABLED=true

# Optional: Set a custom signing secret (auto-generated if not set)
export CCPROXY_SECURITY_API_KEY_SECRET=$(openssl rand -hex 32)
```

### Managing API Keys

```bash
# Create a key for a user (expires in 90 days by default)
ccproxy auth create-key --user john --expires 90

# List all keys
ccproxy auth list-keys

# Revoke a key (soft delete - key remains for audit)
ccproxy auth revoke-key --key-id ccpk_abc123

# Permanently delete a key
ccproxy auth delete-key --key-id ccpk_abc123 --force
```

### Using API Keys

Clients authenticate using the Bearer token:

```bash
curl -H "Authorization: Bearer <your-jwt-token>" \
  https://your-proxy/v1/chat/completions \
  -d '{"model": "claude-3-opus", "messages": [...]}'
```

### Key Features

- **Per-user tracking**: Each key is tied to a user identity
- **Automatic expiration**: Keys expire after configured days
- **Revocation**: Instantly revoke compromised keys
- **Audit trail**: Logs show which user made each request
- **No database required**: Keys are self-validating JWTs

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
claude-code-proxy auth status

# Re-authenticate
claude-code-proxy auth login
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
docker logs claude-code-proxy 2>&1 | grep -i oauth
```

</details>

---

## 🤝 Contributing

Contributions welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md).

## 📄 License

MIT License - see [LICENSE](LICENSE).

## 🙏 Acknowledgments

### Original Project

This fork would not exist without the excellent work by **[@CaddyGlow](https://github.com/CaddyGlow)** on [claude-code-proxy](https://github.com/CaddyGlow/claude-code-proxy).

The original Claude Code Proxy provides:
- Claude proxy architecture with OpenAI format compatibility
- OAuth2 PKCE authentication flows
- SDK and API operating modes
- MCP server integration
- Observability suite (metrics, dashboard, logging)

**If you don't need multi-account rotation, use the [original project](https://github.com/CaddyGlow/claude-code-proxy).**

### Also Thanks To

- [Anthropic](https://anthropic.com) - Claude API & SDK

---

<div align="center">

**[⬆ Back to Top](#claude-code-proxy-multi-account)**

</div>
