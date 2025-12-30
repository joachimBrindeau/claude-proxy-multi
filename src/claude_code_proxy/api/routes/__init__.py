"""API routes for CCProxy API Server."""

from claude_code_proxy.api.routes.claude import router as claude_router
from claude_code_proxy.api.routes.health import router as health_router
from claude_code_proxy.api.routes.proxy import router as proxy_router
from claude_code_proxy.api.routes.root import router as root_router


__all__ = [
    "claude_router",
    "health_router",
    "proxy_router",
    "root_router",
]
