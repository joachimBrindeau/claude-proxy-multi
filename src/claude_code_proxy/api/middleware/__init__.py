"""API middleware for CCProxy API Server."""

from claude_code_proxy.api.middleware.cors import get_cors_config, setup_cors_middleware
from claude_code_proxy.api.middleware.errors import setup_error_handlers


__all__ = [
    "get_cors_config",
    "setup_cors_middleware",
    "setup_error_handlers",
]
