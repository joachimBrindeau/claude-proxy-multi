"""Configuration module for Claude Proxy API Server."""

from claude_code_proxy.exceptions import ConfigValidationError

from .auth import AuthSettings, CredentialStorageSettings, OAuthSettings
from .docker_settings import DockerSettings
from .reverse_proxy import ReverseProxySettings
from .settings import Settings, get_settings


__all__ = [
    "Settings",
    "get_settings",
    "AuthSettings",
    "OAuthSettings",
    "CredentialStorageSettings",
    "ReverseProxySettings",
    "DockerSettings",
    "ConfigValidationError",
]
