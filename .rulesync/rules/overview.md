---
root: true
targets: ["*"]
description: "Claude Proxy Multi project instructions and development guidelines"
globs: ["**/*"]
---

# Claude Proxy Multi Project Instructions

## Protected Directories

**NEVER modify, create, or delete files in these directories:**
- `.claude/` - Claude Code configuration and state
- `specs/` - Feature specifications and planning documents
- `.specify/` - SpecKit configuration and templates

These directories are managed outside of normal development workflows.

## Active Technologies
- Python 3.11+ (existing CCProxy codebase), Shell script (Bash 4+), YAML (GitHub Actions, package configs) (001-universal-deployment)

## Recent Changes
- 001-universal-deployment: Added Python 3.11+ (existing CCProxy codebase), Shell script (Bash 4+), YAML (GitHub Actions, package configs)

## Project Overview

This is **Claude Code Proxy Multi-Account** - a fork of CaddyGlow's claude-code-proxy that adds multi-account rotation with automatic failover for production deployments.

### Key Features
- **3x+ throughput** by distributing requests across multiple Claude accounts
- **Zero downtime** with automatic failover when accounts hit rate limits
- **Hands-off operation** with proactive token refresh before expiration
- **Live updates** via hot-reload - add/remove accounts without restart

### Architecture
- Python 3.11+ with FastAPI
- OAuth2 PKCE authentication flows
- SDK and API operating modes
- OpenAI format compatibility
- Observability suite (Prometheus metrics, DuckDB logs)

### Development Commands
```bash
# Install dependencies
uv sync

# Run development server
uv run claude-code-proxy

# Run tests
uv run pytest

# Type checking
uv run mypy src/

# Linting
uv run ruff check src/
```
