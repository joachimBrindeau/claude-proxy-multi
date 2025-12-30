"""Credentials management package."""

from ccproxy.auth.models import (
    AccountInfo,
    ClaudeCredentials,
    OAuthToken,
    OrganizationInfo,
    UserProfile,
)
from ccproxy.auth.storage import JsonFileTokenStorage as JsonFileStorage
from ccproxy.auth.storage import TokenStorage as CredentialsStorageBackend
from ccproxy.exceptions import (
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
from ccproxy.services.credentials.config import CredentialsConfig, OAuthConfig

# Re-export OAuthSettings - import directly from ccproxy.config.auth to avoid circular imports
# This is intentionally not imported at module level to break circular dependency
from ccproxy.services.credentials.manager import CredentialsManager
from ccproxy.services.credentials.oauth_client import OAuthClient


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
