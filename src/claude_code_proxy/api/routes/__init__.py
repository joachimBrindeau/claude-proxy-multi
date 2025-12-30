"""API routes for Claude Code Proxy API Server."""

from claude_code_proxy.api.routes.accounts import router as accounts_router
from claude_code_proxy.api.routes.claude import router as claude_router
from claude_code_proxy.api.routes.health import router as health_router
from claude_code_proxy.api.routes.proxy import router as proxy_router
from claude_code_proxy.api.routes.root import router as root_router


__all__ = [
    "accounts_router",
    "claude_router",
    "health_router",
    "proxy_router",
    "root_router",
]
