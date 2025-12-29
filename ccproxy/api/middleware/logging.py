"""Access logging middleware for structured HTTP request/response logging."""

import asyncio
import time

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.types import ASGIApp


logger = structlog.get_logger(__name__)


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
        # Record start time
        start_time = time.perf_counter()

        # Extract client info
        client_ip = "unknown"
        if request.client:
            client_ip = request.client.host

        # Extract request info
        method = request.method
        path = str(request.url.path)
        query = str(request.url.query) if request.url.query else None
        user_agent = request.headers.get("user-agent", "unknown")

        # Get request ID from context if available
        request_id: str | None = None
        try:
            if hasattr(request.state, "request_id"):
                request_id = request.state.request_id
            elif hasattr(request.state, "context"):
                context = request.state.context
                if hasattr(context, "request_id"):
                    request_id = context.request_id
        except (AttributeError, KeyError, LookupError):
            pass

        # Process the request
        response: Response | None = None
        error_message: str | None = None

        try:
            response = await call_next(request)
        except (Exception, asyncio.CancelledError) as e:
            error_message = str(e)
            raise
        finally:
            try:
                # Calculate duration
                duration_seconds = time.perf_counter() - start_time
                duration_ms = duration_seconds * 1000

                if response:
                    status_code = response.status_code

                    # Extract rate limit headers if present
                    rate_limit_info = {}
                    anthropic_request_id = None
                    for header_name, header_value in response.headers.items():
                        header_lower = header_name.lower()
                        if header_lower.startswith(
                            "x-ratelimit-"
                        ) or header_lower.startswith("anthropic-ratelimit-"):
                            rate_limit_info[header_lower] = header_value
                        elif header_lower == "request-id":
                            anthropic_request_id = header_value

                    if anthropic_request_id:
                        rate_limit_info["anthropic_request_id"] = anthropic_request_id

                    # Update context metadata if available
                    if hasattr(request.state, "context") and hasattr(
                        request.state.context, "metadata"
                    ):
                        headers = request.state.context.metadata.get("headers", {})
                        headers.update(rate_limit_info)
                        request.state.context.metadata["headers"] = headers
                        request.state.context.metadata["status_code"] = status_code

                    # Log request completion
                    logger.info(
                        "request_complete",
                        request_id=request_id or "unknown",
                        method=method,
                        path=path,
                        status_code=status_code,
                        duration_ms=round(duration_ms, 2),
                        client_ip=client_ip,
                        user_agent=user_agent,
                        query=query,
                        **rate_limit_info,
                    )
                else:
                    # Log error case
                    logger.error(
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
                        exc_info=True,
                    )
            except (
                OSError,
                ValueError,
                AttributeError,
                KeyError,
                LookupError,
            ) as log_error:
                print(f"Failed to write access log: {log_error}")

        return response
