"""API key authentication error responses."""

from fastapi import status
from fastapi.responses import JSONResponse


def create_auth_error_response(
    error: str,
    detail: str,
    status_code: int = status.HTTP_401_UNAUTHORIZED,
) -> JSONResponse:
    """Create a standardized authentication error response.

    Args:
        error: Short error message
        detail: Detailed error description
        status_code: HTTP status code (default: 401)

    Returns:
        JSON response with error information

    """
    return JSONResponse(
        status_code=status_code,
        content={
            "error": error,
            "detail": detail,
        },
        headers={"WWW-Authenticate": "Bearer"},
    )


def missing_token_response() -> JSONResponse:
    """Create response for missing authentication token.

    Returns:
        401 response indicating authentication is required

    """
    return create_auth_error_response(
        error="Authentication required",
        detail="Bearer token required in Authorization header",
    )


def invalid_token_response() -> JSONResponse:
    """Create response for invalid authentication token.

    Returns:
        401 response indicating token is invalid

    """
    return create_auth_error_response(
        error="Invalid API key",
        detail="The provided API key is invalid, expired, or revoked",
    )
