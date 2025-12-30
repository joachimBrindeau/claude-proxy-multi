"""Core error types for the proxy system.

DEPRECATED: This module is deprecated. Import from ccproxy.exceptions instead.
Re-exports are provided for backwards compatibility.
"""

from fastapi import HTTPException

# Import everything from the consolidated exceptions module
from ccproxy.exceptions import (
    AuthenticationError,
    DockerError,
    ModelNotFoundError,
    NotFoundError,
    PermissionAlreadyResolvedError,
    PermissionExpiredError,
    PermissionNotFoundError,
    PermissionRequestError,
    RateLimitError,
    ServiceUnavailableError,
    TimeoutError,
    ValidationError,
)
from ccproxy.exceptions import (
    CCProxyError as ClaudeProxyError,
)
from ccproxy.exceptions import (
    CCProxyError as ProxyError,
)
from ccproxy.exceptions import (
    InsufficientPermissionsError as PermissionError,
)


class ProxyHTTPException(HTTPException):
    """FastAPI HTTPException for proxy errors."""

    pass


# Legacy specialized proxy errors that added metadata
# These are kept for backwards compatibility but could be removed


class TransformationError(ProxyError):
    """Error raised during data transformation.

    DEPRECATED: Use CCProxyError with appropriate error_type instead.
    """

    def __init__(self, message: str, data: object = None) -> None:
        super().__init__(message)
        self.data = data


class MiddlewareError(ProxyError):
    """Error raised during middleware execution.

    DEPRECATED: Use CCProxyError with appropriate error_type instead.
    """

    def __init__(self, message: str, middleware_name: str | None = None) -> None:
        super().__init__(message)
        self.middleware_name = middleware_name


class ProxyConnectionError(ProxyError):
    """Error raised when proxy connection fails.

    DEPRECATED: Use HTTPConnectionError instead.
    """

    def __init__(self, message: str, url: str | None = None) -> None:
        super().__init__(message)
        self.url = url


class ProxyTimeoutError(ProxyError):
    """Error raised when proxy operation times out.

    DEPRECATED: Use HTTPTimeoutError or TimeoutError instead.
    """

    def __init__(self, message: str, timeout: float | None = None) -> None:
        super().__init__(message)
        self.timeout = timeout


class ProxyAuthenticationError(ProxyError):
    """Error raised when proxy authentication fails.

    DEPRECATED: Use AuthenticationError instead.
    """

    def __init__(self, message: str, auth_type: str | None = None) -> None:
        super().__init__(message)
        self.auth_type = auth_type


__all__ = [
    # Legacy core proxy errors
    "ProxyError",
    "TransformationError",
    "MiddlewareError",
    "ProxyConnectionError",
    "ProxyTimeoutError",
    "ProxyAuthenticationError",
    # API-level errors
    "ClaudeProxyError",
    "ValidationError",
    "AuthenticationError",
    "PermissionError",
    "NotFoundError",
    "RateLimitError",
    "ModelNotFoundError",
    "TimeoutError",
    "ServiceUnavailableError",
    "DockerError",
    # Permission errors
    "PermissionRequestError",
    "PermissionNotFoundError",
    "PermissionExpiredError",
    "PermissionAlreadyResolvedError",
    # FastAPI
    "ProxyHTTPException",
]
