"""Rotation middleware for injecting account into requests.

Intercepts requests to inject the selected account into request state,
and handles rate limit errors with automatic retry.

Uses pure ASGI middleware (not BaseHTTPMiddleware) to allow proper retry
since Starlette's BaseHTTPMiddleware cannot call call_next() multiple times.
"""

import orjson
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette import status
from starlette.types import ASGIApp, Message, Receive, Scope, Send
from structlog import get_logger

from ccproxy.rotation.accounts import Account
from ccproxy.rotation.constants import (
    RATE_LIMIT_RETRY_AFTER_SECONDS,
    ROTATION_ENABLED_PATHS,
)
from ccproxy.rotation.pool import RotationPool


logger = get_logger(__name__)

# Header for manual account selection
ACCOUNT_NAME_HEADER = "X-Account-Name"

# Paths that should use rotation (proxy endpoints)
ROTATION_PATHS = list(ROTATION_ENABLED_PATHS)


def _decode_headers(headers: list[tuple[bytes, bytes]]) -> dict[str, str]:
    """Convert ASGI headers (list of byte tuples) to string dict."""
    return {k.decode(): v.decode() for k, v in headers}


class RotationMiddleware:
    """Pure ASGI middleware for account rotation with retry support.

    For each request to rotation-enabled paths:
    1. Selects an account (from header or round-robin)
    2. Injects account into request.state
    3. On rate limit error, retries with different account

    Uses pure ASGI instead of BaseHTTPMiddleware to support retry logic,
    as BaseHTTPMiddleware can only call the app once per request.
    """

    def __init__(
        self,
        app: ASGIApp,
        pool: RotationPool,
        max_retries: int = 3,
    ):
        """Initialize rotation middleware.

        Args:
            app: ASGI application
            pool: Rotation pool for account selection
            max_retries: Maximum retry attempts on rate limit
        """
        self.app = app
        self.pool = pool
        self.max_retries = max_retries

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """ASGI interface."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Check if this path should use rotation
        path = scope.get("path", "")
        if not self._should_rotate_path(path):
            await self.app(scope, receive, send)
            return

        # Read and cache request body for potential retries
        body = await self._read_body(receive)

        # Check for manual account selection
        headers = dict(scope.get("headers", []))
        manual_account_name = headers.get(
            ACCOUNT_NAME_HEADER.lower().encode(),
            headers.get(ACCOUNT_NAME_HEADER.encode()),
        )

        if manual_account_name:
            account_name = (
                manual_account_name.decode()
                if isinstance(manual_account_name, bytes)
                else manual_account_name
            )
            await self._handle_manual_selection(scope, body, send, account_name)
        else:
            await self._handle_automatic_rotation(scope, body, send)

    def _should_rotate_path(self, path: str) -> bool:
        """Check if request path should use rotation."""
        for rotation_path in ROTATION_PATHS:
            if path.startswith(rotation_path) or path == rotation_path:
                return True
        return False

    async def _read_body(self, receive: Receive) -> bytes:
        """Read and return full request body."""
        body_parts = []
        while True:
            message = await receive()
            body = message.get("body", b"")
            if body:
                body_parts.append(body)
            if not message.get("more_body", False):
                break
        return b"".join(body_parts)

    def _create_receive(self, body: bytes) -> Receive:
        """Create a receive callable that returns the cached body."""
        body_sent = False

        async def receive() -> Message:
            nonlocal body_sent
            if not body_sent:
                body_sent = True
                return {"type": "http.request", "body": body, "more_body": False}
            # Return empty body for subsequent calls
            return {"type": "http.request", "body": b"", "more_body": False}

        return receive

    async def _handle_manual_selection(
        self, scope: Scope, body: bytes, send: Send, account_name: str
    ) -> None:
        """Handle request with manually selected account."""
        account = self.pool.get_account(account_name)

        if account is None:
            response = JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={
                    "error": {
                        "type": "account_not_found",
                        "message": f"Account '{account_name}' not found",
                    }
                },
            )
            await response(scope, self._create_receive(body), send)
            return

        if not account.is_available:
            response = JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={
                    "error": {
                        "type": "account_unavailable",
                        "message": f"Account '{account_name}' is {account.state}",
                        "state": account.state,
                    }
                },
            )
            await response(scope, self._create_receive(body), send)
            return

        # Inject account into scope state
        if "state" not in scope:
            scope["state"] = {}
        scope["state"]["rotation_account"] = account
        scope["state"]["rotation_token"] = account.access_token
        scope["state"]["body"] = body
        account.mark_used()

        logger.debug(
            "manual_account_selected",
            account=account_name,
            path=scope.get("path"),
        )

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                status_code = message.get("status", 200)
                # Mark rate limited BEFORE sending response to avoid race condition
                # where httpx receives response before middleware can update pool state
                if status_code == 429:
                    response_headers = list(message.get("headers", []))
                    self.pool.mark_rate_limited(
                        account_name, headers=_decode_headers(response_headers)
                    )
            await send(message)

        await self.app(scope, self._create_receive(body), send_wrapper)

    async def _handle_automatic_rotation(
        self, scope: Scope, body: bytes, send: Send
    ) -> None:
        """Handle request with automatic rotation and retry.

        For non-streaming responses: buffers response to enable retry on 429.
        For streaming responses: passes through immediately (no retry after stream starts).
        """
        tried_accounts: list[str] = []

        for attempt in range(self.max_retries + 1):
            # Get next available account
            if attempt == 0:
                account = await self.pool.get_next_available()
            else:
                account = await self.pool.get_next_available_excluding(tried_accounts)

            if account is None:
                response = self._no_accounts_response(tried_accounts)
                await response(scope, self._create_receive(body), send)
                return

            tried_accounts.append(account.name)

            # Inject account into scope state
            if "state" not in scope:
                scope["state"] = {}
            scope["state"]["rotation_account"] = account
            scope["state"]["rotation_token"] = account.access_token
            scope["state"]["body"] = body

            logger.debug(
                "rotation_attempt",
                account=account.name,
                attempt=attempt + 1,
                path=scope.get("path"),
            )

            # Track response state for potential retry
            response_status_code = status.HTTP_200_OK
            response_headers: list[tuple[bytes, bytes]] = []
            response_body_parts: list[bytes] = []
            is_streaming = False
            response_sent_to_client = False
            should_retry = False

            async def smart_send(message: Message) -> None:
                nonlocal response_status_code, response_headers, is_streaming
                nonlocal response_sent_to_client, should_retry

                if message["type"] == "http.response.start":
                    response_status_code = message.get("status", status.HTTP_200_OK)
                    response_headers = list(message.get("headers", []))

                    # Check if this is a streaming response
                    content_type = ""
                    for name, value in response_headers:
                        if name.lower() == b"content-type":
                            content_type = value.decode().lower()
                            break
                    is_streaming = "text/event-stream" in content_type

                    # For 429 errors, we might retry - don't send yet
                    if (
                        response_status_code == status.HTTP_429_TOO_MANY_REQUESTS
                        and attempt < self.max_retries  # noqa: B023
                    ):
                        should_retry = True
                        return

                    # Mark rate limited BEFORE sending response to avoid race condition
                    if response_status_code == status.HTTP_429_TOO_MANY_REQUESTS:
                        self.pool.mark_rate_limited(
                            account.name,  # noqa: B023
                            headers=_decode_headers(response_headers),  # noqa: B023
                        )

                    # For streaming or non-retryable responses, send immediately
                    await send(message)
                    response_sent_to_client = True

                elif message["type"] == "http.response.body":
                    body_chunk = message.get("body", b"")

                    # If we're potentially retrying, buffer the response
                    if should_retry:
                        if body_chunk:
                            response_body_parts.append(body_chunk)  # noqa: B023
                        return

                    # Otherwise send immediately
                    await send(message)

            # Call the app
            await self.app(scope, self._create_receive(body), smart_send)

            # Check for rate limit error - retry if we have more accounts
            if (
                response_status_code == status.HTTP_429_TOO_MANY_REQUESTS
                and should_retry
            ):
                logger.info(
                    "rate_limit_detected_retrying",
                    account=account.name,
                    attempt=attempt + 1,
                )

                # Mark account as rate limited
                self.pool.mark_rate_limited(
                    account.name, headers=_decode_headers(response_headers)
                )

                # Clear for next attempt
                response_body_parts.clear()
                continue

            # If we got 429 but ran out of retries, send the buffered response
            if (
                response_status_code == status.HTTP_429_TOO_MANY_REQUESTS
                and not response_sent_to_client
            ):
                # Mark account as rate limited BEFORE sending response
                # to avoid race condition with client processing response
                self.pool.mark_rate_limited(
                    account.name, headers=_decode_headers(response_headers)
                )

                await send(
                    {
                        "type": "http.response.start",
                        "status": response_status_code,
                        "headers": response_headers,
                    }
                )
                await send(
                    {
                        "type": "http.response.body",
                        "body": b"".join(response_body_parts),
                        "more_body": False,
                    }
                )

            # Check for auth error (response already sent to client)
            if response_status_code in (
                status.HTTP_401_UNAUTHORIZED,
                status.HTTP_403_FORBIDDEN,
            ):
                error_msg = self._extract_error_from_body(b"".join(response_body_parts))
                self.pool.mark_auth_error(
                    account.name, error_msg or "Authentication failed"
                )

            return

        # All retries exhausted (shouldn't normally reach here)
        response = self._all_accounts_exhausted_response(tried_accounts)
        await response(scope, self._create_receive(body), send)

    def _no_accounts_response(self, tried: list[str]) -> JSONResponse:
        """Response when no accounts are available."""
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "error": {
                    "type": "no_accounts_available",
                    "message": "No Claude accounts available for requests",
                    "totalAccounts": self.pool.account_count,
                    "rateLimited": self.pool.rate_limited_count,
                    "authErrors": self.pool.auth_error_count,
                }
            },
        )

    def _all_accounts_exhausted_response(self, tried: list[str]) -> JSONResponse:
        """Response when all retry attempts exhausted."""
        pool_status = self.pool.get_status()

        # Find earliest rate limit reset
        reset_times = [
            a["rateLimitedUntil"]
            for a in pool_status["accounts"]
            if a.get("rateLimitedUntil")
        ]
        earliest_reset = min(reset_times) if reset_times else None

        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "error": {
                    "type": "all_accounts_rate_limited",
                    "message": "All accounts are rate limited",
                    "triedAccounts": tried,
                    "retryAfter": earliest_reset,
                }
            },
            headers={"Retry-After": RATE_LIMIT_RETRY_AFTER_SECONDS},
        )

    def _extract_error_from_body(self, body: bytes) -> str | None:
        """Extract error message from response body."""
        try:
            if body:
                data = orjson.loads(body)
                if "error" in data:
                    msg = data["error"].get("message")
                    return str(msg) if msg else None
        except orjson.JSONDecodeError:
            # Response body is not valid JSON - ignore and return None
            pass
        return None


def get_rotation_account(request: Request) -> Account | None:
    """Get the rotation account from request state.

    Helper function for route handlers to access the selected account.

    Args:
        request: FastAPI request

    Returns:
        Account if set by middleware, None otherwise
    """
    account: Account | None = getattr(request.state, "rotation_account", None)
    return account


def get_rotation_token(request: Request) -> str | None:
    """Get the access token from rotation account in request state.

    Helper function to get the token for API calls.

    Args:
        request: FastAPI request

    Returns:
        Access token if rotation account set, None otherwise
    """
    account = get_rotation_account(request)
    if account:
        token: str = account.access_token
        return token
    return None
