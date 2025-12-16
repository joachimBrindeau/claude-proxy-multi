"""Token refresh scheduler for proactive OAuth token management.

Handles automatic token refresh before expiration with exponential backoff
on failures. Persists refreshed tokens to accounts.json.
"""

import asyncio
from datetime import UTC, datetime

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from structlog import get_logger

from ccproxy.auth.oauth.token_exchange import (
    TokenExchangeError,
    refresh_token_async,
)
from ccproxy.rotation.accounts import AccountCredentials
from ccproxy.rotation.pool import RotationPool


logger = get_logger(__name__)

# Refresh settings
REFRESH_CHECK_INTERVAL_SECONDS = 60  # Check every minute
REFRESH_BUFFER_SECONDS = 600  # Refresh 10 minutes before expiry
MAX_REFRESH_RETRIES = 3
INITIAL_RETRY_DELAY_SECONDS = 5


class TokenRefreshScheduler:
    """Background scheduler for proactive token refresh.

    Features:
    - Checks all accounts every minute
    - Refreshes tokens within 10 minutes of expiration
    - Retries with exponential backoff on failures
    - Persists refreshed tokens immediately
    - Marks accounts as auth_error if refresh token is invalid
    """

    def __init__(
        self,
        pool: RotationPool,
        check_interval: int = REFRESH_CHECK_INTERVAL_SECONDS,
        refresh_buffer: int = REFRESH_BUFFER_SECONDS,
    ):
        """Initialize token refresh scheduler.

        Args:
            pool: Rotation pool to manage
            check_interval: Seconds between refresh checks
            refresh_buffer: Refresh when expiring within this many seconds
        """
        self.pool = pool
        self.check_interval = check_interval
        self.refresh_buffer = refresh_buffer
        self._scheduler: AsyncIOScheduler | None = None
        self._http_client: httpx.AsyncClient | None = None
        self._running = False

    async def start(self) -> None:
        """Start the refresh scheduler."""
        if self._running:
            logger.warning("refresh_scheduler_already_running")
            return

        self._http_client = httpx.AsyncClient(timeout=30.0)
        self._scheduler = AsyncIOScheduler()

        self._scheduler.add_job(
            self._check_and_refresh_all,
            "interval",
            seconds=self.check_interval,
            id="token_refresh_check",
            name="Token Refresh Check",
        )

        self._scheduler.start()
        self._running = True

        logger.info(
            "token_refresh_scheduler_started",
            check_interval=self.check_interval,
            refresh_buffer=self.refresh_buffer,
        )

        # Run initial check immediately
        asyncio.create_task(self._check_and_refresh_all())

    async def stop(self) -> None:
        """Stop the refresh scheduler."""
        if not self._running:
            return

        if self._scheduler:
            self._scheduler.shutdown(wait=False)
            self._scheduler = None

        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None

        self._running = False
        logger.info("token_refresh_scheduler_stopped")

    async def _check_and_refresh_all(self) -> None:
        """Check all accounts and refresh tokens as needed."""
        accounts = self.pool.get_all_accounts()

        for account in accounts:
            # Skip accounts with auth errors (need manual intervention)
            if account.state == "auth_error":
                continue

            # Check if token needs refresh
            if account.credentials.needs_refresh(self.refresh_buffer):
                logger.info(
                    "token_refresh_needed",
                    account=account.name,
                    expires_in=account.credentials.expires_in_seconds,
                )
                await self._refresh_with_retry(account.name)

    async def _refresh_with_retry(self, account_name: str) -> bool:
        """Refresh token with exponential backoff on failure.

        Args:
            account_name: Name of account to refresh

        Returns:
            True if refresh succeeded
        """
        account = self.pool.get_account(account_name)
        if not account:
            return False

        delay = INITIAL_RETRY_DELAY_SECONDS

        for attempt in range(MAX_REFRESH_RETRIES):
            try:
                new_credentials = await self._refresh_token(
                    account.credentials.refresh_token
                )

                # Update account with new credentials
                self.pool.update_credentials(
                    account_name, new_credentials, persist=True
                )

                # If account was rate limited due to expired token, restore it
                if account.state == "rate_limited":
                    self.pool.mark_available(account_name)

                logger.info(
                    "token_refresh_success",
                    account=account_name,
                    new_expires_in=new_credentials.expires_in_seconds,
                )
                return True

            except RefreshTokenExpiredError as e:
                # Refresh token itself is invalid - needs manual re-auth
                logger.error(
                    "refresh_token_expired",
                    account=account_name,
                    error=str(e),
                )
                self.pool.mark_auth_error(
                    account_name,
                    "Refresh token expired. Please re-authenticate."
                )
                return False

            except RefreshTokenError as e:
                # Transient error - retry with backoff
                logger.warning(
                    "token_refresh_retry",
                    account=account_name,
                    attempt=attempt + 1,
                    max_attempts=MAX_REFRESH_RETRIES,
                    delay=delay,
                    error=str(e),
                )

                if attempt < MAX_REFRESH_RETRIES - 1:
                    await asyncio.sleep(delay)
                    delay *= 2  # Exponential backoff

        # All retries failed
        logger.error(
            "token_refresh_failed",
            account=account_name,
            attempts=MAX_REFRESH_RETRIES,
        )

        # Don't mark as auth_error for transient failures
        # The token might still be valid for a while
        return False

    async def _refresh_token(self, refresh_token_value: str) -> AccountCredentials:
        """Refresh an OAuth token using centralized token exchange.

        Args:
            refresh_token_value: Refresh token to use

        Returns:
            New credentials with refreshed tokens

        Raises:
            RefreshTokenExpiredError: If refresh token is invalid
            RefreshTokenError: On other refresh failures
        """
        try:
            data = await refresh_token_async(refresh_token_value)
        except TokenExchangeError as e:
            # Check for expired/invalid refresh token
            response_text = e.response_text or ""
            is_invalid_grant = "invalid_grant" in response_text.lower()
            is_expired = "expired" in response_text.lower()
            if e.status_code == 400 and (is_invalid_grant or is_expired):
                raise RefreshTokenExpiredError(
                    f"Refresh token is invalid or expired: {response_text}"
                ) from e
            raise RefreshTokenError(f"Token refresh failed: {e}") from e

        # Parse response
        access_token = data.get("access_token")
        new_refresh_token = data.get("refresh_token", refresh_token_value)
        expires_in = data.get("expires_in", 3600)

        if not access_token:
            raise RefreshTokenError("No access_token in refresh response")

        # Calculate expiration timestamp
        expires_at = int(
            (datetime.now(UTC).timestamp() + expires_in) * 1000
        )

        return AccountCredentials(
            access_token=access_token,
            refresh_token=new_refresh_token,
            expires_at=expires_at,
        )

    async def refresh_account_now(self, account_name: str) -> bool:
        """Manually trigger token refresh for an account.

        Args:
            account_name: Name of account to refresh

        Returns:
            True if refresh succeeded
        """
        return await self._refresh_with_retry(account_name)


class RefreshTokenError(Exception):
    """Error during token refresh (may be transient)."""

    pass


class RefreshTokenExpiredError(RefreshTokenError):
    """Refresh token is expired or invalid (needs manual intervention)."""

    pass


# Global scheduler instance
_scheduler: TokenRefreshScheduler | None = None


def get_refresh_scheduler() -> TokenRefreshScheduler:
    """Get the global refresh scheduler instance.

    Returns:
        TokenRefreshScheduler instance

    Raises:
        RuntimeError: If scheduler not initialized
    """
    if _scheduler is None:
        raise RuntimeError("Token refresh scheduler not initialized")
    return _scheduler


def init_refresh_scheduler(pool: RotationPool) -> TokenRefreshScheduler:
    """Initialize the global refresh scheduler.

    Args:
        pool: Rotation pool to manage

    Returns:
        Initialized TokenRefreshScheduler
    """
    global _scheduler
    _scheduler = TokenRefreshScheduler(pool)
    return _scheduler
