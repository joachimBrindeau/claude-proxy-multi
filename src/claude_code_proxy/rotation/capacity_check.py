"""Account capacity checker using Claude API rate limit headers.

Makes a minimal API call through the local proxy to retrieve current rate limit
status for an account. Uses the /api/v1/messages endpoint which:
1. Goes through rotation middleware (honors X-Account-Name header)
2. Applies proper OAuth headers (anthropic-beta: oauth-2025-04-20, x-app: cli)
3. Makes direct HTTP call to api.anthropic.com with rotation account's token

Note: Do NOT use /sdk/v1/messages - that ignores rotation tokens and uses CLI credentials.

Example:
    >>> from claude_code_proxy.rotation.capacity_check import check_capacity_async
    >>> capacity = await check_capacity_async("my-account")
    >>> if capacity.error:
    ...     print(f"Error: {capacity.error}")
    >>> else:
    ...     print(f"Tokens remaining: {capacity.tokens_remaining_percent:.1f}%")
"""

import contextlib
import os
import warnings
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx
from structlog import get_logger
from tenacity import (
    AsyncRetrying,
    RetryError,
    retry_if_exception,
    stop_after_attempt,
    wait_fixed,
)
from typing_extensions import TypedDict


logger = get_logger(__name__)

# Configuration for capacity checks
# Environment variables:
# - CCPROXY_CAPACITY_CHECK_URL: Proxy URL for capacity checks
#   Default: http://localhost:8000/api/v1/messages (internal container port)
#   Docker: Use localhost:8000 (not 8100) for internal requests
# - CCPROXY_CAPACITY_CHECK_MODEL: Model to use for minimal requests
#   Default: claude-sonnet-4-20250514
DEFAULT_PROXY_URL = os.getenv(
    "CCPROXY_CAPACITY_CHECK_URL", "http://localhost:8000/api/v1/messages"
)

DEFAULT_CAPACITY_CHECK_MODEL = os.getenv(
    "CCPROXY_CAPACITY_CHECK_MODEL", "claude-sonnet-4-20250514"
)


class CapacityInfoDict(TypedDict):
    """Typed dictionary for CapacityInfo.to_dict() return value."""

    tokens_limit: int | None
    tokens_remaining: int | None
    tokens_remaining_percent: float | None
    tokens_reset: str | None
    requests_limit: int | None
    requests_remaining: int | None
    requests_remaining_percent: float | None
    requests_reset: str | None
    is_rate_limited: bool
    error: str | None
    checked_at: str | None


@dataclass
class CapacityInfo:
    """Rate limit capacity information for an account."""

    # Token limits (per minute typically)
    tokens_limit: int | None = None
    tokens_remaining: int | None = None
    tokens_reset: str | None = None  # ISO8601 timestamp

    # Request limits (per minute typically)
    requests_limit: int | None = None
    requests_remaining: int | None = None
    requests_reset: str | None = None  # ISO8601 timestamp

    # Error info if check failed
    error: str | None = None
    checked_at: datetime | None = None

    @property
    def tokens_remaining_percent(self) -> float | None:
        """Calculate percentage of tokens remaining."""
        if self.tokens_limit and self.tokens_remaining is not None:
            return (self.tokens_remaining / self.tokens_limit) * 100
        return None

    @property
    def requests_remaining_percent(self) -> float | None:
        """Calculate percentage of requests remaining."""
        if self.requests_limit and self.requests_remaining is not None:
            return (self.requests_remaining / self.requests_limit) * 100
        return None

    @property
    def is_rate_limited(self) -> bool:
        """Check if account appears to be rate limited."""
        # Consider rate limited if less than 5% remaining
        token_pct = self.tokens_remaining_percent
        if token_pct is not None and token_pct < 5:
            return True
        req_pct = self.requests_remaining_percent
        return bool(req_pct is not None and req_pct < 5)

    def to_dict(self) -> CapacityInfoDict:
        """Convert to dictionary for JSON serialization."""
        return CapacityInfoDict(
            tokens_limit=self.tokens_limit,
            tokens_remaining=self.tokens_remaining,
            tokens_remaining_percent=self.tokens_remaining_percent,
            tokens_reset=self.tokens_reset,
            requests_limit=self.requests_limit,
            requests_remaining=self.requests_remaining,
            requests_remaining_percent=self.requests_remaining_percent,
            requests_reset=self.requests_reset,
            is_rate_limited=self.is_rate_limited,
            error=self.error,
            checked_at=self.checked_at.isoformat() if self.checked_at else None,
        )


# --- Shared Helper Functions ---


def _build_capacity_request(
    account_name: str,
    model: str,
) -> tuple[dict[str, str], dict[str, Any]]:
    """Build headers and body for capacity check request.

    Returns:
        Tuple of (headers, body) for the request
    """
    headers = {
        "Content-Type": "application/json",
        "X-Account-Name": account_name,
    }

    body = {
        "model": model,
        "max_tokens": 1,
        "messages": [{"role": "user", "content": "Hi"}],
    }

    return headers, body


def _parse_rate_limit_headers(headers: httpx.Headers) -> CapacityInfo:
    """Parse Anthropic rate limit headers into CapacityInfo.

    Headers format:
    - anthropic-ratelimit-tokens-limit: 40000
    - anthropic-ratelimit-tokens-remaining: 39500
    - anthropic-ratelimit-tokens-reset: 2024-01-01T00:00:00Z
    - anthropic-ratelimit-requests-limit: 50
    - anthropic-ratelimit-requests-remaining: 49
    - anthropic-ratelimit-requests-reset: 2024-01-01T00:00:00Z
    """
    info = CapacityInfo(checked_at=datetime.now(UTC))

    # Token limits
    if tokens_limit := headers.get("anthropic-ratelimit-tokens-limit"):
        with contextlib.suppress(ValueError):
            info.tokens_limit = int(tokens_limit)

    if tokens_remaining := headers.get("anthropic-ratelimit-tokens-remaining"):
        with contextlib.suppress(ValueError):
            info.tokens_remaining = int(tokens_remaining)

    if tokens_reset := headers.get("anthropic-ratelimit-tokens-reset"):
        info.tokens_reset = tokens_reset

    # Request limits
    if requests_limit := headers.get("anthropic-ratelimit-requests-limit"):
        with contextlib.suppress(ValueError):
            info.requests_limit = int(requests_limit)

    if requests_remaining := headers.get("anthropic-ratelimit-requests-remaining"):
        with contextlib.suppress(ValueError):
            info.requests_remaining = int(requests_remaining)

    if requests_reset := headers.get("anthropic-ratelimit-requests-reset"):
        info.requests_reset = requests_reset

    return info


def _process_capacity_response(
    response: httpx.Response,
    account_name: str,
    proxy_url: str,
) -> CapacityInfo:
    """Process capacity check response and return CapacityInfo.

    Parses rate limit headers and sets appropriate error messages.

    Args:
        response: HTTP response from proxy
        account_name: Account name for logging
        proxy_url: Proxy URL for debugging info

    Returns:
        CapacityInfo with parsed rate limit data and any errors
    """
    info = _parse_rate_limit_headers(response.headers)

    if response.status_code == 401:
        info.error = "Authentication failed - token may be invalid or expired"
        logger.warning(
            "capacity_check_auth_error",
            account=account_name,
            status=response.status_code,
        )
    elif response.status_code == 429:
        info.error = "Account is currently rate limited"
        logger.info(
            "capacity_check_rate_limited",
            account=account_name,
            status=response.status_code,
        )
    elif response.status_code == 503:
        info.error = "Anthropic API temporarily unavailable - try again"
        logger.info(
            "capacity_check_service_unavailable",
            account=account_name,
            status=response.status_code,
        )
    elif response.status_code == 529:
        info.error = "Anthropic API overloaded - try again later"
        logger.info(
            "capacity_check_overloaded",
            account=account_name,
            status=response.status_code,
        )
    elif response.status_code >= 400:
        info.error = f"API error: {response.status_code}"
        logger.warning(
            "capacity_check_api_error",
            account=account_name,
            status=response.status_code,
            body=response.text[:200],
            proxy_url=proxy_url,
        )
    else:
        logger.info(
            "capacity_check_success",
            account=account_name,
            tokens_remaining=info.tokens_remaining,
            tokens_limit=info.tokens_limit,
            requests_remaining=info.requests_remaining,
        )

    return info


def _make_error_info(error: str) -> CapacityInfo:
    """Create CapacityInfo with an error message."""
    return CapacityInfo(
        error=error,
        checked_at=datetime.now(UTC),
    )


# --- Public API ---


# Transient errors that should be retried (503 Service Unavailable, 529 Overloaded)
TRANSIENT_STATUS_CODES = frozenset({503, 529})


class _TransientCapacityError(Exception):
    """Internal: Transient error during capacity check that should be retried.

    This is an internal implementation detail for retry logic.
    Not exported in __all__.
    """

    def __init__(self, status_code: int, info: CapacityInfo):
        self.status_code = status_code
        self.info = info
        super().__init__(f"Transient error: {status_code}")


def _should_retry_capacity_check(exception: BaseException) -> bool:
    """Determine if an exception should trigger a retry."""
    return isinstance(
        exception,
        httpx.TimeoutException | httpx.RequestError | _TransientCapacityError,
    )


def _log_capacity_retry(retry_state: Any, account_name: str) -> None:
    """Log retry attempts before sleeping."""
    exc = retry_state.outcome.exception() if retry_state.outcome else None
    wait_seconds = retry_state.next_action.sleep if retry_state.next_action else 0

    if isinstance(exc, _TransientCapacityError):
        logger.info(
            "capacity_check_retry",
            account=account_name,
            status=exc.status_code,
            attempt=retry_state.attempt_number,
            wait_seconds=wait_seconds,
        )
    else:
        logger.info(
            "capacity_check_retry",
            account=account_name,
            attempt=retry_state.attempt_number,
            wait_seconds=wait_seconds,
            error=str(exc) if exc else None,
        )


async def _perform_capacity_check(
    proxy_url: str,
    headers: dict[str, str],
    body: dict[str, Any],
    account_name: str,
    timeout: float,
) -> CapacityInfo:
    """Perform a single capacity check request.

    Args:
        proxy_url: URL of the local proxy endpoint
        headers: Request headers
        body: Request body
        account_name: Account name for logging
        timeout: Request timeout

    Returns:
        CapacityInfo from response

    Raises:
        _TransientCapacityError: For retryable errors (503, 529)
    """
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(proxy_url, headers=headers, json=body)
        info = _process_capacity_response(response, account_name, proxy_url)

        # Raise exception for transient errors to trigger retry
        if response.status_code in TRANSIENT_STATUS_CODES:
            raise _TransientCapacityError(response.status_code, info)

        return info


def _handle_capacity_check_error(
    error: BaseException, account_name: str
) -> CapacityInfo:
    """Handle and convert capacity check errors to CapacityInfo.

    Args:
        error: Exception that occurred
        account_name: Account name for logging

    Returns:
        CapacityInfo with error message
    """
    if isinstance(error, httpx.TimeoutException):
        return _make_error_info("Request timed out")
    if isinstance(error, httpx.RequestError):
        return _make_error_info(f"Request failed: {error}")
    if isinstance(error, _TransientCapacityError):
        return error.info
    if isinstance(error, RetryError) and error.last_attempt.exception():
        exc = error.last_attempt.exception()
        if isinstance(exc, _TransientCapacityError):
            return exc.info
        return _make_error_info(str(exc))
    if isinstance(error, RetryError):
        return _make_error_info("All retry attempts exhausted")

    logger.exception("capacity_check_unexpected_error", account=account_name)
    return _make_error_info(f"Unexpected error: {error}")


async def check_capacity_async(
    account_name: str,
    timeout: float = 30.0,
    model: str = DEFAULT_CAPACITY_CHECK_MODEL,
    proxy_url: str = DEFAULT_PROXY_URL,
    max_retries: int = 2,
) -> CapacityInfo:
    """Check account capacity by making a minimal API call through the proxy (async).

    This is the recommended function for use in FastAPI endpoints and other async code.

    Makes a minimal messages request with max_tokens=1 to get rate limit headers
    without consuming significant quota. Routes through /api/v1/messages which
    applies OAuth headers and uses the rotation account's token.

    Automatically retries on transient errors (503, 529).

    Args:
        account_name: Name of the account to check (uses X-Account-Name header)
        timeout: Request timeout in seconds
        model: Model to use for the capacity check request
        proxy_url: URL of the local proxy endpoint
        max_retries: Maximum retry attempts for transient errors (503, 529)

    Returns:
        CapacityInfo with rate limit information or error
    """
    headers, body = _build_capacity_request(account_name, model)

    try:
        async for attempt in AsyncRetrying(
            wait=wait_fixed(1),
            stop=stop_after_attempt(max_retries + 1),
            retry=retry_if_exception(_should_retry_capacity_check),
            before_sleep=lambda rs: _log_capacity_retry(rs, account_name),
            reraise=True,
        ):
            with attempt:
                return await _perform_capacity_check(
                    proxy_url, headers, body, account_name, timeout
                )

    except (
        httpx.TimeoutException,
        httpx.RequestError,
        httpx.HTTPStatusError,
        httpx.InvalidURL,
        ValueError,
        TypeError,
        _TransientCapacityError,
        RetryError,
    ) as e:
        return _handle_capacity_check_error(e, account_name)


def check_capacity_sync(
    account_name: str,
    timeout: float = 30.0,
    model: str = DEFAULT_CAPACITY_CHECK_MODEL,
    proxy_url: str = DEFAULT_PROXY_URL,
) -> CapacityInfo:
    """Check account capacity using synchronous HTTP client.

    WARNING: This function blocks the event loop and should NOT be used in:
    - FastAPI endpoints (async contexts)
    - Event loop contexts
    - High-concurrency scenarios

    This function makes synchronous HTTP calls that will block the calling thread.
    For FastAPI and async code, use check_capacity_async() instead.

    This function is provided for CLI tools and synchronous scripts only.

    Args:
        account_name: Name of the account to check (uses X-Account-Name header)
        timeout: Request timeout in seconds
        model: Model to use for the capacity check request
        proxy_url: URL of the local proxy endpoint

    Returns:
        CapacityInfo with rate limit information or error
    """
    warnings.warn(
        "check_capacity_sync() blocks the event loop. "
        "Use check_capacity_async() in async code.",
        stacklevel=2,
    )

    headers, body = _build_capacity_request(account_name, model)

    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(proxy_url, headers=headers, json=body)
            return _process_capacity_response(response, account_name, proxy_url)

    except httpx.TimeoutException:
        return _make_error_info("Request timed out")
    except httpx.RequestError as e:
        return _make_error_info(f"Request failed: {e}")
    except (httpx.HTTPStatusError, httpx.InvalidURL, ValueError, TypeError) as e:
        # httpx.HTTPStatusError: Non-retryable HTTP errors
        # httpx.InvalidURL: Malformed proxy URL
        # ValueError/TypeError: Unexpected response format or parsing errors
        logger.exception("capacity_check_unexpected_error", account=account_name)
        return _make_error_info(f"Unexpected error: {e}")
