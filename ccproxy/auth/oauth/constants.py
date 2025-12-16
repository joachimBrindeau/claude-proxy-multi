"""OAuth constants shared across all OAuth implementations.

This module provides a single source of truth for OAuth configuration
to prevent scope divergence and inconsistencies across the codebase.

IMPORTANT: Redirect URI Dependency
=====================================
The available OAuth scopes depend on the redirect_uri being used:

1. Localhost redirect (http://localhost:*/callback):
   - Can include: org:create_api_key
   - Used by: CLI with local callback server

2. Console redirect (https://console.anthropic.com/oauth/code/callback):
   - CANNOT include: org:create_api_key (causes 400 errors)
   - Must include: user:sessions:claude_code (for Claude Code client)
   - Used by: Web UI, headless servers (manual code paste)

Current Configuration
=====================
We use the CONSOLE redirect URI pattern because:
- Works in any environment (no localhost required)
- Compatible with Docker containers and remote servers
- Supports manual code paste workflow

HAR Analysis Evidence
=====================
Testing showed org:create_api_key scope fails with console redirect:
- Request: POST https://claude.ai/v1/oauth/{org_uuid}/authorize
- Scopes: ["org:create_api_key", "user:profile", "user:inference"]
- Redirect: https://console.anthropic.com/oauth/code/callback
- Response: 400 {"type":"error","error":{"type":"invalid_request_error"}}

This scope appears restricted to localhost redirect URIs for security.

References
==========
- Anthropic OAuth Docs: https://docs.anthropic.com/en/api/oauth
- Claude CLI source: Uses localhost redirect with org:create_api_key
- Session: 2025-12-14 OAuth debugging with HAR analysis
"""

# OAuth Authorization Server
OAUTH_AUTHORIZE_URL = "https://claude.ai/oauth/authorize"
OAUTH_TOKEN_URL = "https://console.anthropic.com/v1/oauth/token"

# Client Configuration
OAUTH_CLIENT_ID = "9d1c250a-e61b-44d9-88ed-5944d1962f5e"
OAUTH_REDIRECT_URI = "https://console.anthropic.com/oauth/code/callback"

# API Headers
OAUTH_BETA_VERSION = "oauth-2025-04-20"
OAUTH_USER_AGENT = "Claude-Code/1.0.43"

# Scopes (optimized for console redirect URI)
# NOTE: org:create_api_key intentionally excluded - only works with localhost
OAUTH_SCOPES = [
    "user:profile",           # User profile information
    "user:inference",         # API inference access
    "user:sessions:claude_code",  # Required for Claude Code client
]
