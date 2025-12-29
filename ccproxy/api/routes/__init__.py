"""API routes for CCProxy API Server."""

from ccproxy.api.routes.claude import router as claude_router
from ccproxy.api.routes.health import router as health_router
from ccproxy.api.routes.proxy import router as proxy_router


__all__ = [
    "claude_router",
    "health_router",
    "proxy_router",
]
