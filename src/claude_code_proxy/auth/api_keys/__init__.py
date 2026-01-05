"""API key authentication module."""

from claude_code_proxy.auth.api_keys.config import (
    DEFAULT_PUBLIC_ROUTES,
    PublicRoutesConfig,
)
from claude_code_proxy.auth.api_keys.jwt_handler import JWTHandler
from claude_code_proxy.auth.api_keys.manager import APIKeyManager
from claude_code_proxy.auth.api_keys.models import APIKey, APIKeyCreate
from claude_code_proxy.auth.api_keys.storage import APIKeyStorage


__all__ = [
    "DEFAULT_PUBLIC_ROUTES",
    "APIKey",
    "APIKeyCreate",
    "APIKeyManager",
    "APIKeyStorage",
    "JWTHandler",
    "PublicRoutesConfig",
]
