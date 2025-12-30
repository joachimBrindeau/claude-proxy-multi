"""Credentials management package."""

from claude_code_proxy.auth.models import (
    AccountInfo,
    ClaudeCredentials,
    OAuthToken,
    OrganizationInfo,
    UserProfile,
)
from claude_code_proxy.auth.storage import JsonFileTokenStorage as JsonFileStorage
from claude_code_proxy.auth.storage import TokenStorage as CredentialsStorageBackend
from claude_code_proxy.exceptions import (
    CredentialsError,
    CredentialsExpiredError,
    CredentialsInvalidError,
    CredentialsNotFoundError,
    CredentialsStorageError,
    OAuthCallbackError,
    OAuthError,
    OAuthLoginError,
    OAuthTokenRefreshError,
)
from claude_code_proxy.services.credentials.config import CredentialsConfig, OAuthConfig

# Re-export OAuthSettings - import directly from claude_code_proxy.config.auth to avoid circular imports
# This is intentionally not imported at module level to break circular dependency
from claude_code_proxy.services.credentials.manager import CredentialsManager
from claude_code_proxy.services.credentials.oauth_client import OAuthClient


__all__ = [
    # Manager
    "CredentialsManager",
    # Config
    "CredentialsConfig",
    "OAuthConfig",  # Backwards compatibility alias
    # Models
    "ClaudeCredentials",
    "OAuthToken",
    "OrganizationInfo",
    "AccountInfo",
    "UserProfile",
    # Storage
    "CredentialsStorageBackend",
    "JsonFileStorage",
    # OAuth
    "OAuthClient",
    # Exceptions
    "CredentialsError",
    "CredentialsNotFoundError",
    "CredentialsInvalidError",
    "CredentialsExpiredError",
    "CredentialsStorageError",
    "OAuthError",
    "OAuthLoginError",
    "OAuthTokenRefreshError",
    "OAuthCallbackError",
]
