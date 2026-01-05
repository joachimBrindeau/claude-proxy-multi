"""Access logging middleware for structured HTTP request/response logging."""

import asyncio
import time
from typing import Any

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.types import ASGIApp


logger = structlog.get_logger(__name__)


def _extract_request_id(request: Request) -> str | None:
    """Extract request ID from request state if available."""
    try:
        if hasattr(request.state, "request_id"):
            request_id = request.state.request_id
            return str(request_id) if request_id is not None else None
        if hasattr(request.state, "context"):
            context = request.state.context
            if hasattr(context, "request_id"):
                request_id = context.request_id
                return str(request_id) if request_id is not None else None
    except (AttributeError, KeyError, LookupError):
        pass
    return None


def _extract_rate_limit_info(response: Response) -> dict[str, Any]:
    """Extract rate limit headers from response."""
    rate_limit_info: dict[str, Any] = {}
    anthropic_request_id = None

    for header_name, header_value in response.headers.items():
        header_lower = header_name.lower()
        if header_lower.startswith(("x-ratelimit-", "anthropic-ratelimit-")):
            rate_limit_info[header_lower] = header_value
        elif header_lower == "request-id":
            anthropic_request_id = header_value

    if anthropic_request_id:
        rate_limit_info["anthropic_request_id"] = anthropic_request_id

    return rate_limit_info


def _update_context_metadata(
    request: Request, rate_limit_info: dict[str, Any], status_code: int
) -> None:
    """Update request context metadata with response info."""
    if not hasattr(request.state, "context"):
        return
    if not hasattr(request.state.context, "metadata"):
        return

    headers = request.state.context.metadata.get("headers", {})
    headers.update(rate_limit_info)
    request.state.context.metadata["headers"] = headers
    request.state.context.metadata["status_code"] = status_code


class AccessLogMiddleware(BaseHTTPMiddleware):
    """Middleware for structured access logging with request/response details."""

    def __init__(self, app: ASGIApp):
        """Initialize the access log middleware.

        Args:
            app: The ASGI application

        """
        super().__init__(app)

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        """Process the request and log access details.

        Args:
            request: The incoming HTTP request
            call_next: The next middleware/handler in the chain

        Returns:
            The HTTP response

        """
        start_time = time.perf_counter()
        client_ip = request.client.host if request.client else "unknown"
        method = request.method
        path = str(request.url.path)
        query = str(request.url.query) if request.url.query else None
        user_agent = request.headers.get("user-agent", "unknown")
        request_id = _extract_request_id(request)

        response: Response | None = None
        error_message: str | None = None

        try:
            response = await call_next(request)
        except (Exception, asyncio.CancelledError) as e:
            error_message = str(e)
            raise
        finally:
            self._log_request(
                request=request,
                response=response,
                start_time=start_time,
                request_id=request_id,
                method=method,
                path=path,
                query=query,
                client_ip=client_ip,
                user_agent=user_agent,
                error_message=error_message,
            )

        return response

    def _log_request(
        self,
        *,
        request: Request,
        response: Response | None,
        start_time: float,
        request_id: str | None,
        method: str,
        path: str,
        query: str | None,
        client_ip: str,
        user_agent: str,
        error_message: str | None,
    ) -> None:
        """Log request completion or error."""
        try:
            duration_seconds = time.perf_counter() - start_time
            duration_ms = duration_seconds * 1000

            if response:
                rate_limit_info = _extract_rate_limit_info(response)
                _update_context_metadata(request, rate_limit_info, response.status_code)

                logger.info(
                    "request_complete",
                    request_id=request_id or "unknown",
                    method=method,
                    path=path,
                    status_code=response.status_code,
                    duration_ms=round(duration_ms, 2),
                    client_ip=client_ip,
                    user_agent=user_agent,
                    query=query,
                    **rate_limit_info,
                )
            else:
                logger.exception(
                    "request_error",
                    request_id=request_id,
                    method=method,
                    path=path,
                    query=query,
                    client_ip=client_ip,
                    user_agent=user_agent,
                    duration_ms=duration_ms,
                    duration_seconds=duration_seconds,
                    error_message=error_message or "No response generated",
                )
        except (OSError, ValueError, AttributeError, KeyError, LookupError) as e:
            print(f"Failed to write access log: {e}")
