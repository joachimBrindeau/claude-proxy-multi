"""Request ID middleware for generating and tracking request IDs."""

import shortuuid
import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.types import ASGIApp

from claude_code_proxy.core.request_context import RequestContext


logger = structlog.get_logger(__name__)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Middleware for generating request IDs and initializing request context."""

    def __init__(self, app: ASGIApp):
        """Initialize the request ID middleware.

        Args:
            app: The ASGI application

        """
        super().__init__(app)

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        """Process the request and add request ID/context.

        Args:
            request: The incoming HTTP request
            call_next: The next middleware/handler in the chain

        Returns:
            The HTTP response

        """
        # Generate or extract request ID
        request_id = request.headers.get("x-request-id") or shortuuid.uuid()

        # Create minimal context
        ctx = RequestContext(
            request_id=request_id,
            method=request.method,
            path=str(request.url.path),
        )

        # Store context in request state for access by services
        request.state.request_id = request_id
        request.state.context = ctx

        # Process the request
        response = await call_next(request)

        # Add request ID to response headers
        response.headers["x-request-id"] = request_id

        return response
