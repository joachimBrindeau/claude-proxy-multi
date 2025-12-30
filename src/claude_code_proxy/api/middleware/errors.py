"""Error handling middleware for CCProxy API Server.

Provides unified error handling for all CCProxyError subclasses
using their built-in error_type and status_code attributes.
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from starlette import status
from starlette.exceptions import HTTPException as StarletteHTTPException
from structlog import get_logger

from claude_code_proxy.exceptions import CCProxyError


logger = get_logger(__name__)


def _store_status_code(request: Request, status_code: int) -> None:
    """Store status code in request state for access logging."""
    if hasattr(request.state, "context") and hasattr(request.state.context, "metadata"):
        request.state.context.metadata["status_code"] = status_code


def _get_client_ip(request: Request) -> str:
    """Get client IP from request."""
    return request.client.host if request.client else "unknown"


def _build_error_response(
    status_code: int, error_type: str, message: str
) -> JSONResponse:
    """Build standardized error response."""
    return JSONResponse(
        status_code=status_code,
        content={"error": {"type": error_type, "message": message}},
    )


def setup_error_handlers(app: FastAPI) -> None:
    """Setup error handlers for the FastAPI application."""
    logger.debug("error_handlers_setup_start")

    @app.exception_handler(CCProxyError)
    async def ccproxy_error_handler(
        request: Request, exc: CCProxyError
    ) -> JSONResponse:
        """Handle all CCProxyError subclasses using their built-in attributes."""
        _store_status_code(request, exc.status_code)

        # Get error_type as string
        error_type = (
            exc.error_type.value
            if hasattr(exc.error_type, "value")
            else str(exc.error_type)
        )

        # Log with appropriate context based on error type
        log_kwargs = {
            "error_type": error_type,
            "error_message": str(exc),
            "status_code": exc.status_code,
            "request_method": request.method,
            "request_url": str(request.url.path),
        }

        # Add client IP for auth-related errors
        if exc.status_code in (401, 403, 429):
            log_kwargs["client_ip"] = _get_client_ip(request)

        logger.error(f"{type(exc).__name__}", **log_kwargs)

        return _build_error_response(exc.status_code, error_type, str(exc))

    @app.exception_handler(HTTPException)
    async def http_exception_handler(
        request: Request, exc: HTTPException
    ) -> JSONResponse:
        """Handle FastAPI HTTP exceptions."""
        _store_status_code(request, exc.status_code)

        log_kwargs = {
            "error_type": f"http_{exc.status_code}",
            "error_message": exc.detail,
            "status_code": exc.status_code,
            "request_method": request.method,
            "request_url": str(request.url.path),
        }

        # Use appropriate log level based on status code
        if exc.status_code == 404:
            logger.debug("HTTP 404", **log_kwargs)
        elif exc.status_code == 401:
            logger.warning("HTTP 401", **log_kwargs)
        else:
            logger.error("HTTP exception", **log_kwargs)

        return _build_error_response(exc.status_code, "http_error", exc.detail)

    @app.exception_handler(StarletteHTTPException)
    async def starlette_http_exception_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        """Handle Starlette HTTP exceptions."""
        log_kwargs = {
            "error_type": f"starlette_http_{exc.status_code}",
            "error_message": exc.detail,
            "status_code": exc.status_code,
            "request_method": request.method,
            "request_url": str(request.url.path),
        }

        if exc.status_code == 404:
            logger.debug("Starlette HTTP 404", **log_kwargs)
        else:
            logger.error("Starlette HTTP exception", **log_kwargs)

        return _build_error_response(exc.status_code, "http_error", exc.detail)

    @app.exception_handler(Exception)
    async def global_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        """Handle all other unhandled exceptions."""
        _store_status_code(request, status.HTTP_500_INTERNAL_SERVER_ERROR)

        logger.error(
            "Unhandled exception",
            error_type="unhandled_exception",
            error_message=str(exc),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            request_method=request.method,
            request_url=str(request.url.path),
            exc_info=True,
        )

        return _build_error_response(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "internal_server_error",
            "An internal server error occurred",
        )

    logger.debug("error_handlers_setup_completed")
