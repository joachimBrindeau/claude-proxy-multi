"""Authentication exceptions.

DEPRECATED: This module is deprecated. Import from ccproxy.exceptions instead.
Re-exports are provided for backwards compatibility.
"""

from ccproxy.exceptions import (
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


__all__ = [
    "AuthenticationError",
    "AuthenticationRequiredError",
    "InvalidTokenError",
    "InsufficientPermissionsError",
    "CredentialsError",
    "CredentialsNotFoundError",
    "CredentialsExpiredError",
    "CredentialsInvalidError",
    "CredentialsStorageError",
    "OAuthError",
    "OAuthLoginError",
    "OAuthTokenRefreshError",
    "OAuthCallbackError",
]
