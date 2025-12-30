"""Consolidated exception hierarchy for CCProxy.

All exceptions use proper exception chaining with the `from` keyword.
Exception groups are used for collecting multiple related errors (Python 3.11+).
Error types use StrEnum for type safety and autocompletion.
"""

from enum import StrEnum
from typing import Any

from starlette import status


class ErrorType(StrEnum):
    """Error type codes for API responses."""

    INVALID_REQUEST = "invalid_request_error"
    AUTHENTICATION = "authentication_error"
    PERMISSION = "permission_error"
    NOT_FOUND = "not_found_error"
    RATE_LIMIT = "rate_limit_error"
    TIMEOUT = "timeout_error"
    SERVICE_UNAVAILABLE = "service_unavailable_error"
    INTERNAL_SERVER = "internal_server_error"
    DOCKER = "docker_error"
    EXPIRED = "expired_error"
    CONFLICT = "conflict_error"


# ============================================================================
# Base Exceptions
# ============================================================================


class CCProxyError(Exception):
    """Base exception for all CCProxy errors.

    All exceptions inherit from this base class for easy catching.
    Supports HTTP status codes and structured error details.
    """

    def __init__(
        self,
        message: str,
        *,
        error_type: ErrorType | str = ErrorType.INTERNAL_SERVER,
        status_code: int = 500,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        # Convert string error_type to ErrorType if possible
        if isinstance(error_type, str) and not isinstance(error_type, ErrorType):
            try:
                self.error_type = ErrorType(error_type)
            except ValueError:
                # Keep as string if not a valid ErrorType value
                self.error_type = error_type  # type: ignore[assignment]
        else:
            self.error_type = error_type
        self.status_code = status_code
        self.details = details or {}


# ============================================================================
# HTTP & Network Errors
# ============================================================================


class HTTPError(CCProxyError):
    """Base exception for HTTP client errors."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int = 500,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            error_type=ErrorType.INTERNAL_SERVER,
            status_code=status_code,
            details=details,
        )


class HTTPTimeoutError(HTTPError):
    """Exception raised when HTTP request times out."""

    def __init__(self, message: str = "Request timed out") -> None:
        super().__init__(message, status_code=status.HTTP_408_REQUEST_TIMEOUT)


class HTTPConnectionError(HTTPError):
    """Exception raised when HTTP connection fails."""

    def __init__(self, message: str = "Connection failed") -> None:
        super().__init__(message, status_code=status.HTTP_503_SERVICE_UNAVAILABLE)


# ============================================================================
# API Errors (Client-facing)
# ============================================================================


class ValidationError(CCProxyError):
    """Validation error (400)."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(
            message,
            error_type=ErrorType.INVALID_REQUEST,
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details,
        )


class AuthenticationError(CCProxyError):
    """Authentication error (401)."""

    def __init__(self, message: str = "Authentication failed") -> None:
        super().__init__(
            message,
            error_type=ErrorType.AUTHENTICATION,
            status_code=status.HTTP_401_UNAUTHORIZED,
        )


class AuthenticationRequiredError(AuthenticationError):
    """Authentication is required but not provided."""

    pass


class InvalidTokenError(AuthenticationError):
    """Invalid or expired token."""

    pass


class InsufficientPermissionsError(CCProxyError):
    """Insufficient permissions for the requested operation (403)."""

    def __init__(self, message: str = "Permission denied") -> None:
        super().__init__(
            message,
            error_type=ErrorType.PERMISSION,
            status_code=status.HTTP_403_FORBIDDEN,
        )


class NotFoundError(CCProxyError):
    """Not found error (404)."""

    def __init__(self, message: str = "Resource not found") -> None:
        super().__init__(
            message,
            error_type=ErrorType.NOT_FOUND,
            status_code=status.HTTP_404_NOT_FOUND,
        )


class RateLimitError(CCProxyError):
    """Rate limit error (429)."""

    def __init__(self, message: str = "Rate limit exceeded") -> None:
        super().__init__(
            message,
            error_type=ErrorType.RATE_LIMIT,
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        )


class TimeoutError(CCProxyError):
    """Request timeout error (408)."""

    def __init__(self, message: str = "Request timeout") -> None:
        super().__init__(
            message,
            error_type=ErrorType.TIMEOUT,
            status_code=status.HTTP_408_REQUEST_TIMEOUT,
        )


class ServiceUnavailableError(CCProxyError):
    """Service unavailable error (503)."""

    def __init__(self, message: str = "Service temporarily unavailable") -> None:
        super().__init__(
            message,
            error_type=ErrorType.SERVICE_UNAVAILABLE,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )


class ModelNotFoundError(NotFoundError):
    """Model not found error (404)."""

    def __init__(self, model: str) -> None:
        super().__init__(f"Model '{model}' not found")


# ============================================================================
# Configuration & Validation Errors
# ============================================================================


class ConfigValidationError(CCProxyError):
    """Configuration validation error."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(
            message,
            error_type=ErrorType.INVALID_REQUEST,
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details,
        )


# ============================================================================
# Credentials & OAuth Errors
# ============================================================================


class CredentialsError(AuthenticationError):
    """Base credentials error."""

    pass


class CredentialsNotFoundError(CredentialsError):
    """Credentials not found error."""

    pass


class CredentialsExpiredError(CredentialsError):
    """Credentials expired error."""

    pass


class CredentialsInvalidError(CredentialsError):
    """Credentials are invalid or malformed."""

    pass


class CredentialsStorageError(CredentialsError):
    """Error occurred during credentials storage operations."""

    pass


class OAuthError(AuthenticationError):
    """Base OAuth error."""

    pass


class OAuthLoginError(OAuthError):
    """OAuth login failed."""

    pass


class OAuthTokenRefreshError(OAuthError):
    """OAuth token refresh failed."""

    pass


class OAuthCallbackError(OAuthError):
    """OAuth callback failed."""

    pass


class TokenExchangeError(OAuthError):
    """Token exchange failed during OAuth flow."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        response_text: str | None = None,
    ):
        super().__init__(message)
        if status_code is not None:
            self.status_code = status_code
        self.response_text = response_text


# ============================================================================
# Permission & Confirmation Errors
# ============================================================================


class PermissionRequestError(CCProxyError):
    """Base exception for permission request-related errors."""

    pass


class PermissionNotFoundError(PermissionRequestError):
    """Raised when permission request is not found."""

    def __init__(self, confirmation_id: str) -> None:
        super().__init__(
            f"Permission request '{confirmation_id}' not found",
            error_type=ErrorType.NOT_FOUND,
            status_code=status.HTTP_404_NOT_FOUND,
        )


class PermissionExpiredError(PermissionRequestError):
    """Raised when permission request has expired."""

    def __init__(self, confirmation_id: str) -> None:
        super().__init__(
            f"Permission request '{confirmation_id}' has expired",
            error_type=ErrorType.EXPIRED,
            status_code=status.HTTP_410_GONE,
        )


class PermissionAlreadyResolvedError(PermissionRequestError):
    """Raised when trying to resolve an already resolved request."""

    def __init__(self, confirmation_id: str, resolution_status: str) -> None:
        super().__init__(
            f"Permission request '{confirmation_id}' already resolved with status: {resolution_status}",
            error_type=ErrorType.CONFLICT,
            status_code=status.HTTP_409_CONFLICT,
        )


# ============================================================================
# Claude SDK Errors
# ============================================================================


class ClaudeSDKError(CCProxyError):
    """Base Claude SDK error."""

    pass


class StreamTimeoutError(ClaudeSDKError):
    """Stream timeout error when no SDK message is received within timeout."""

    def __init__(self, message: str, session_id: str, timeout_seconds: float):
        super().__init__(message)
        self.session_id = session_id
        self.timeout_seconds = timeout_seconds


# ============================================================================
# Scheduler Errors
# ============================================================================


class SchedulerError(CCProxyError):
    """Base exception for scheduler-related errors."""

    pass


class TaskRegistrationError(SchedulerError):
    """Raised when task registration fails."""

    pass


class TaskNotFoundError(SchedulerError):
    """Raised when attempting to access a task that doesn't exist."""

    pass


class TaskExecutionError(SchedulerError):
    """Raised when task execution encounters an error."""

    def __init__(self, task_name: str, original_error: Exception):
        super().__init__(f"Task '{task_name}' execution failed: {original_error}")
        self.task_name = task_name
        self.original_error = original_error


class SchedulerShutdownError(SchedulerError):
    """Raised when scheduler shutdown encounters an error."""

    pass


# ============================================================================
# Docker Errors
# ============================================================================


class DockerError(CCProxyError):
    """Docker operation error."""

    def __init__(
        self,
        message: str,
        *,
        command: str | None = None,
        cause: Exception | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        error_details = details or {}
        if command:
            error_details["command"] = command
        if cause:
            error_details["cause"] = str(cause)

        super().__init__(
            message,
            error_type=ErrorType.DOCKER,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=error_details,
        )


__all__ = [
    # Enums
    "ErrorType",
    # Base
    "CCProxyError",
    # HTTP & Network
    "HTTPError",
    "HTTPTimeoutError",
    "HTTPConnectionError",
    # API Errors
    "ValidationError",
    "AuthenticationError",
    "AuthenticationRequiredError",
    "InvalidTokenError",
    "InsufficientPermissionsError",
    "NotFoundError",
    "RateLimitError",
    "TimeoutError",
    "ServiceUnavailableError",
    "ModelNotFoundError",
    # Configuration
    "ConfigValidationError",
    # Credentials & OAuth
    "CredentialsError",
    "CredentialsNotFoundError",
    "CredentialsExpiredError",
    "CredentialsInvalidError",
    "CredentialsStorageError",
    "OAuthError",
    "OAuthLoginError",
    "OAuthTokenRefreshError",
    "OAuthCallbackError",
    "TokenExchangeError",
    # Permissions
    "PermissionRequestError",
    "PermissionNotFoundError",
    "PermissionExpiredError",
    "PermissionAlreadyResolvedError",
    # Claude SDK
    "ClaudeSDKError",
    "StreamTimeoutError",
    # Scheduler
    "SchedulerError",
    "TaskRegistrationError",
    "TaskNotFoundError",
    "TaskExecutionError",
    "SchedulerShutdownError",
    # Docker
    "DockerError",
]
