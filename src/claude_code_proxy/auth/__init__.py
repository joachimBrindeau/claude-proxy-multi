"""Authentication module for centralized auth handling."""

from claude_code_proxy.auth.bearer import BearerTokenAuthManager
from claude_code_proxy.auth.credentials_adapter import CredentialsAuthManager
from claude_code_proxy.auth.dependencies import (
    AccessTokenDep,
    AuthManagerDep,
    RequiredAuthDep,
    get_access_token,
    get_auth_manager,
    get_bearer_auth_manager,
    get_credentials_auth_manager,
    require_auth,
)
from claude_code_proxy.auth.manager import AuthManager, BaseAuthManager
from claude_code_proxy.auth.storage import (
    JsonFileTokenStorage,
    KeyringTokenStorage,
    TokenStorage,
)
from claude_code_proxy.exceptions import (
    AuthenticationError,
    AuthenticationRequiredError,
    CredentialsError,
    CredentialsExpiredError,
    CredentialsInvalidError,
    CredentialsNotFoundError,
    CredentialsStorageError,
    InsufficientPermissionsError,
    InvalidTokenError,
    OAuthCallbackError,
    OAuthError,
    OAuthLoginError,
    OAuthTokenRefreshError,
)
from claude_code_proxy.services.credentials.manager import CredentialsManager


__all__ = [
    # Manager interfaces
    "AuthManager",
    "BaseAuthManager",
    # Implementations
    "BearerTokenAuthManager",
    "CredentialsAuthManager",
    "CredentialsManager",
    # Storage interfaces and implementations
    "TokenStorage",
    "JsonFileTokenStorage",
    "KeyringTokenStorage",
    # Exceptions
    "AuthenticationError",
    "AuthenticationRequiredError",
    "CredentialsError",
    "CredentialsExpiredError",
    "CredentialsInvalidError",
    "CredentialsNotFoundError",
    "CredentialsStorageError",
    "InvalidTokenError",
    "InsufficientPermissionsError",
    "OAuthCallbackError",
    "OAuthError",
    "OAuthLoginError",
    "OAuthTokenRefreshError",
    # Dependencies
    "get_auth_manager",
    "get_bearer_auth_manager",
    "get_credentials_auth_manager",
    "require_auth",
    "get_access_token",
    # Type aliases
    "AuthManagerDep",
    "RequiredAuthDep",
    "AccessTokenDep",
]
