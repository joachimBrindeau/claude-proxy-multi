"""API key authentication middleware for protecting routes."""

from pathlib import Path

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.types import ASGIApp

from claude_code_proxy.auth.api_keys import (
    DEFAULT_PUBLIC_ROUTES,
    APIKeyManager,
    PublicRoutesConfig,
)
from claude_code_proxy.auth.api_keys.errors import (
    invalid_token_response,
    missing_token_response,
)
from claude_code_proxy.config.settings import Settings


logger = structlog.get_logger(__name__)


class APIKeyAuthMiddleware(BaseHTTPMiddleware):
    """Middleware for API key authentication on all routes."""

    def __init__(
        self,
        app: ASGIApp,
        settings: Settings,
        public_routes: PublicRoutesConfig | None = None,
    ):
        """Initialize the API key auth middleware.

        Args:
            app: The ASGI application
            settings: Application settings
            public_routes: Optional custom public routes configuration

        """
        super().__init__(app)
        self.settings = settings
        self.public_routes = public_routes or DEFAULT_PUBLIC_ROUTES
        self.api_key_manager: APIKeyManager | None = None

        # Initialize API key manager if enabled
        if settings.security.api_keys_enabled and settings.security.api_key_secret:
            storage_path = Path(settings.auth.storage.api_keys_file)
            self.api_key_manager = APIKeyManager(
                storage_path=storage_path,
                secret_key=settings.security.api_key_secret,
            )

    def _extract_bearer_token(self, request: Request) -> str | None:
        """Extract bearer token from Authorization header.

        Args:
            request: The incoming request

        Returns:
            Bearer token if found, None otherwise

        """
        auth_header = request.headers.get("authorization")
        if not auth_header:
            return None

        # Parse "Bearer <token>"
        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return None

        return parts[1]

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        """Process the request with API key authentication.

        Args:
            request: The incoming HTTP request
            call_next: The next middleware/handler in the chain

        Returns:
            The HTTP response or 401 Unauthorized

        """
        path = request.url.path

        # Allow public routes without auth
        if self.public_routes.is_public(path):
            return await call_next(request)

        # If API keys not enabled, allow all requests
        if not self.settings.security.api_keys_enabled or not self.api_key_manager:
            return await call_next(request)

        # Extract and validate API key
        token = self._extract_bearer_token(request)
        if not token:
            logger.warning(
                "api_key_auth_missing",
                path=path,
                method=request.method,
            )
            return missing_token_response()

        # Validate the API key
        api_key = self.api_key_manager.validate_key(token)
        if not api_key:
            logger.warning(
                "api_key_auth_invalid",
                path=path,
                method=request.method,
            )
            return invalid_token_response()

        # Store authenticated user info in request state
        request.state.api_key = api_key
        request.state.user_id = api_key.user_id

        logger.debug(
            "api_key_auth_success",
            user_id=api_key.user_id,
            key_id=api_key.key_id,
            path=path,
        )

        # Continue to the route handler
        return await call_next(request)
