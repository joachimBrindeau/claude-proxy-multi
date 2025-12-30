"""Rotation pool for managing multiple Claude accounts.

Provides round-robin account selection with rate limit failover
and automatic state management.
"""

import asyncio
import re
from collections.abc import Iterator
from datetime import UTC, datetime
from enum import StrEnum
from itertools import cycle, islice
from pathlib import Path
from typing import Any

from dateutil import parser as dateutil_parser
from structlog import get_logger

from ccproxy.rotation.accounts import (
    DEFAULT_ACCOUNTS_PATH,
    Account,
    AccountCredentials,
    AccountsFile,
    load_accounts,
    save_accounts,
)


logger = get_logger(__name__)


class AccountState(StrEnum):
    """Account availability states."""

    AVAILABLE = "available"
    RATE_LIMITED = "rate_limited"
    AUTH_ERROR = "auth_error"
    DISABLED = "disabled"


# Rate limit detection patterns
RATE_LIMIT_PATTERNS = [
    re.compile(r"rate.?limit", re.IGNORECASE),
    re.compile(r"usage.?limit", re.IGNORECASE),
    re.compile(r"exceeded", re.IGNORECASE),
    re.compile(r"too.?many.?requests", re.IGNORECASE),
]


def is_rate_limit_error(status_code: int, error_message: str | None = None) -> bool:
    """Check if an error indicates rate limiting.

    Args:
        status_code: HTTP status code
        error_message: Optional error message to check

    Returns:
        True if this appears to be a rate limit error
    """
    # HTTP 429 is always rate limit
    if status_code == 429:
        return True

    # Check error message patterns
    if error_message:
        for pattern in RATE_LIMIT_PATTERNS:
            if pattern.search(error_message):
                return True

    return False


def parse_retry_after(headers: dict[str, str]) -> int | None:
    """Parse rate limit reset time from response headers.

    Checks headers in order of preference:
    1. retry-after (seconds or HTTP date)
    2. anthropic-ratelimit-unified-reset (Unix timestamp - new MAX format)
    3. anthropic-ratelimit-unified-7d-reset (Unix timestamp - 7-day window)
    4. anthropic-ratelimit-tokens-reset (ISO8601 timestamp - legacy)
    5. anthropic-ratelimit-requests-reset (ISO8601 timestamp - legacy)

    Args:
        headers: Response headers (case-insensitive lookup)

    Returns:
        Unix timestamp (ms) when rate limit resets, or None
    """
    # Build case-insensitive header map
    headers_lower = {k.lower(): v for k, v in headers.items()}

    # Log rate limit headers for debugging
    rate_limit_headers = {
        k: v for k, v in headers_lower.items() if "ratelimit" in k or k == "retry-after"
    }
    if rate_limit_headers:
        logger.info("rate_limit_headers_received", headers=rate_limit_headers)

    # Try retry-after first
    retry_after = headers_lower.get("retry-after")
    if retry_after is not None:
        try:
            # Try parsing as seconds
            seconds = int(retry_after)
            reset_ms = int(datetime.now(UTC).timestamp() * 1000) + (seconds * 1000)
            logger.info("retry_after_parsed", seconds=seconds, reset_ms=reset_ms)
            return reset_ms
        except ValueError:
            pass

        try:
            # Try parsing as HTTP date (RFC 2822) or ISO8601
            dt = dateutil_parser.parse(retry_after)
            # Ensure timezone-aware datetime (assume UTC if naive)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
            reset_ms = int(dt.timestamp() * 1000)
            logger.info("retry_after_parsed_date", date=retry_after, reset_ms=reset_ms)
            return reset_ms
        except (ValueError, TypeError, dateutil_parser.ParserError):
            pass

    # Try new unified rate limit headers (Unix timestamps in seconds)
    # These are used by Claude MAX subscriptions
    for header_name in (
        "anthropic-ratelimit-unified-reset",
        "anthropic-ratelimit-unified-7d-reset",
    ):
        if reset_value := headers_lower.get(header_name):
            try:
                # Parse as Unix timestamp (seconds)
                reset_seconds = int(reset_value)
                reset_ms = reset_seconds * 1000
                reset_dt = datetime.fromtimestamp(reset_seconds, tz=UTC)
                logger.info(
                    "unified_ratelimit_parsed",
                    header=header_name,
                    value=reset_value,
                    reset_time=reset_dt.isoformat(),
                    reset_ms=reset_ms,
                )
                return reset_ms
            except (ValueError, TypeError):
                pass

    # Fall back to legacy Anthropic headers (ISO8601 timestamps)
    for header_name in (
        "anthropic-ratelimit-tokens-reset",
        "anthropic-ratelimit-requests-reset",
    ):
        if reset_value := headers_lower.get(header_name):
            try:
                # Parse ISO8601 timestamp (e.g., "2024-01-01T00:00:00Z")
                dt = dateutil_parser.parse(reset_value)
                # Ensure timezone-aware datetime (assume UTC if naive)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=UTC)
                reset_ms = int(dt.timestamp() * 1000)
                logger.info(
                    "ratelimit_reset_parsed",
                    header=header_name,
                    value=reset_value,
                    reset_ms=reset_ms,
                )
                return reset_ms
            except (ValueError, TypeError, dateutil_parser.ParserError):
                pass

    logger.warning(
        "no_retry_after_header_found", available_headers=list(headers_lower.keys())
    )
    return None


class RotationPool:
    """Manages a pool of Claude accounts with round-robin rotation.

    Features:
    - Round-robin account selection
    - Automatic rate limit detection and failover
    - State tracking for each account
    - Thread-safe operations
    """

    def __init__(
        self,
        accounts_path: Path | None = None,
        auto_load: bool = True,
    ):
        """Initialize rotation pool.

        Args:
            accounts_path: Path to accounts.json file
            auto_load: Whether to load accounts on init
        """
        self._accounts_path = accounts_path or DEFAULT_ACCOUNTS_PATH
        self._accounts: dict[str, Account] = {}
        self._account_order: list[str] = []  # For consistent round-robin
        self._account_cycle: Iterator[str] | None = None
        self._lock = asyncio.Lock()
        self._last_modified: float | None = None

        if auto_load:
            try:
                self.load()
            except FileNotFoundError:
                logger.warning(
                    "accounts_file_not_found",
                    path=str(self._accounts_path),
                    message="Rotation pool initialized empty - create accounts.json to add accounts",
                )

    @property
    def accounts_path(self) -> Path:
        """Get the accounts file path."""
        return Path(self._accounts_path).expanduser()

    @property
    def account_count(self) -> int:
        """Get total number of accounts."""
        return len(self._accounts)

    @property
    def available_count(self) -> int:
        """Get number of available accounts."""
        self._check_rate_limit_resets()
        return sum(1 for a in self._accounts.values() if a.is_available)

    @property
    def rate_limited_count(self) -> int:
        """Get number of rate-limited accounts."""
        return sum(
            1 for a in self._accounts.values() if a.state == AccountState.RATE_LIMITED
        )

    @property
    def auth_error_count(self) -> int:
        """Get number of accounts with auth errors."""
        return sum(
            1 for a in self._accounts.values() if a.state == AccountState.AUTH_ERROR
        )

    def _copy_capacity_state(self, source: Account, target: Account) -> None:
        """Copy capacity-related runtime state from source to target account.

        Args:
            source: Account to copy state from
            target: Account to copy state to
        """
        target.last_used = source.last_used
        target.tokens_limit = source.tokens_limit
        target.tokens_remaining = source.tokens_remaining
        target.tokens_remaining_percent = source.tokens_remaining_percent
        target.requests_limit = source.requests_limit
        target.requests_remaining = source.requests_remaining
        target.requests_remaining_percent = source.requests_remaining_percent
        target.capacity_checked_at = source.capacity_checked_at

    def load(self) -> None:
        """Load accounts from file.

        Preserves runtime state (rate limits, capacity info, etc.) for existing accounts.
        Only credentials are updated from the file.

        If credentials have changed (new refresh_token), resets auth_error state
        since the user has re-authenticated.
        """
        accounts_file = load_accounts(self._accounts_path)
        new_accounts = accounts_file.accounts

        # Preserve runtime state for existing accounts
        for name, new_account in new_accounts.items():
            if name in self._accounts:
                existing = self._accounts[name]

                # Detect if credentials have changed (user re-authenticated)
                credentials_changed = (
                    existing.credentials.refresh_token
                    != new_account.credentials.refresh_token
                )

                # If credentials changed and account was in auth_error, restore it
                if credentials_changed and existing.state == AccountState.AUTH_ERROR:
                    logger.info(
                        "account_credentials_refreshed_clearing_auth_error",
                        account=name,
                        previous_error=existing.last_error,
                    )
                    # Keep new_account state as default "available"
                    # Preserve only capacity state (not error state)
                    self._copy_capacity_state(existing, new_account)
                else:
                    # Preserve all runtime state including error state
                    new_account.state = existing.state
                    new_account.rate_limited_until = existing.rate_limited_until
                    new_account.last_error = existing.last_error
                    self._copy_capacity_state(existing, new_account)
                    logger.debug(
                        "account_state_preserved",
                        account=name,
                        state=existing.state,
                        rate_limited_until=existing.rate_limited_until,
                    )

        self._accounts = new_accounts
        self._account_order = list(self._accounts.keys())

        # Initialize cycle iterator for round-robin rotation
        if self._account_order:
            self._account_cycle = cycle(self._account_order)
        else:
            self._account_cycle = None

        # Track file modification time
        path = self.accounts_path
        if path.exists():
            self._last_modified = path.stat().st_mtime

        logger.info(
            "rotation_pool_loaded",
            accounts=self._account_order,
            count=len(self._accounts),
        )

    def save(self) -> bool:
        """Save accounts to file (persists token updates)."""
        accounts_file = AccountsFile(version=1, accounts=self._accounts)
        success = save_accounts(accounts_file, self._accounts_path)

        if success:
            # Update last modified time
            path = self.accounts_path
            if path.exists():
                self._last_modified = path.stat().st_mtime

        return success

    def _check_rate_limit_resets(self) -> None:
        """Check and reset any accounts whose rate limits have expired."""
        for account in self._accounts.values():
            account.check_rate_limit_reset()

    def get_account(self, name: str) -> Account | None:
        """Get account by name.

        Args:
            name: Account name

        Returns:
            Account if found, None otherwise
        """
        return self._accounts.get(name)

    def get_all_accounts(self) -> list[Account]:
        """Get all accounts."""
        return list(self._accounts.values())

    def get_available_accounts(self) -> list[Account]:
        """Get all available accounts."""
        self._check_rate_limit_resets()
        return [a for a in self._accounts.values() if a.is_available]

    async def get_next_available(self) -> Account | None:
        """Get the next available account using round-robin.

        This is the main entry point for account selection.
        Automatically handles rate limit resets.

        Returns:
            Next available account, or None if all unavailable
        """
        async with self._lock:
            self._check_rate_limit_resets()

            if not self._account_order or not self._account_cycle:
                logger.warning("no_accounts_configured")
                return None

            # Try each account in round-robin order using cycle iterator
            for account_name in islice(self._account_cycle, len(self._account_order)):
                account = self._accounts.get(account_name)

                if account and account.is_available:
                    account.mark_used()
                    logger.debug(
                        "account_selected",
                        account=account.name,
                    )
                    return account

            # All accounts unavailable
            logger.warning(
                "all_accounts_unavailable",
                total=len(self._accounts),
                rate_limited=self.rate_limited_count,
                auth_error=self.auth_error_count,
            )
            return None

    async def get_next_available_excluding(
        self,
        exclude: list[str],
    ) -> Account | None:
        """Get next available account excluding specified accounts.

        Used for retry logic - excludes accounts that already failed.

        Args:
            exclude: List of account names to skip

        Returns:
            Next available account not in exclude list, or None
        """
        async with self._lock:
            self._check_rate_limit_resets()

            if not self._account_order or not self._account_cycle:
                return None

            # Try each account in round-robin order using cycle iterator
            for account_name in islice(self._account_cycle, len(self._account_order)):
                if account_name in exclude:
                    continue

                account = self._accounts.get(account_name)
                if account and account.is_available:
                    account.mark_used()
                    logger.debug(
                        "account_selected_excluding",
                        account=account.name,
                        excluded=exclude,
                    )
                    return account

            return None

    def mark_rate_limited(
        self,
        account_name: str,
        reset_time: int | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        """Mark an account as rate limited.

        Args:
            account_name: Name of the account
            reset_time: Optional reset timestamp (ms)
            headers: Optional response headers to parse retry-after
        """
        account = self._accounts.get(account_name)
        if not account:
            logger.warning("unknown_account_rate_limited", account=account_name)
            return

        # Try to get reset time from headers if not provided
        if reset_time is None and headers:
            reset_time = parse_retry_after(headers)

        account.mark_rate_limited(reset_time)

    def mark_auth_error(self, account_name: str, error: str) -> None:
        """Mark an account as having authentication error.

        Args:
            account_name: Name of the account
            error: Error message
        """
        account = self._accounts.get(account_name)
        if not account:
            logger.warning("unknown_account_auth_error", account=account_name)
            return

        account.mark_auth_error(error)

    def mark_available(self, account_name: str) -> None:
        """Mark an account as available again.

        Args:
            account_name: Name of the account
        """
        account = self._accounts.get(account_name)
        if not account:
            logger.warning("unknown_account_mark_available", account=account_name)
            return

        account.mark_available()

    def update_credentials(
        self,
        account_name: str,
        new_credentials: AccountCredentials,
        persist: bool = True,
    ) -> bool:
        """Update credentials for an account.

        Args:
            account_name: Name of the account
            new_credentials: New credentials
            persist: Whether to save to file

        Returns:
            True if updated successfully
        """
        account = self._accounts.get(account_name)
        if not account:
            logger.warning("unknown_account_credential_update", account=account_name)
            return False

        account.update_credentials(new_credentials)

        if persist:
            return self.save()

        return True

    def add_account(self, account: Account) -> bool:
        """Add a new account to the pool.

        Args:
            account: Account to add

        Returns:
            True if added (False if name already exists)
        """
        if account.name in self._accounts:
            logger.warning("account_already_exists", account=account.name)
            return False

        self._accounts[account.name] = account
        self._account_order.append(account.name)

        # Reinitialize cycle iterator with new account list
        self._account_cycle = cycle(self._account_order)

        logger.info("account_added", account=account.name)
        return True

    def remove_account(self, account_name: str) -> bool:
        """Remove an account from the pool.

        Args:
            account_name: Name of account to remove

        Returns:
            True if removed (False if not found)
        """
        if account_name not in self._accounts:
            logger.warning("account_not_found", account=account_name)
            return False

        del self._accounts[account_name]
        self._account_order.remove(account_name)

        # Reinitialize cycle iterator with updated account list
        if self._account_order:
            self._account_cycle = cycle(self._account_order)
        else:
            self._account_cycle = None

        logger.info("account_removed", account=account_name)
        return True

    def has_file_changed(self) -> bool:
        """Check if accounts file has been modified since last load.

        Returns:
            True if file has changed
        """
        path = self.accounts_path
        if not path.exists():
            return self._last_modified is not None

        current_mtime = path.stat().st_mtime
        return current_mtime != self._last_modified

    def reload_if_changed(self) -> bool:
        """Reload accounts if file has changed.

        Returns:
            True if reloaded
        """
        if self.has_file_changed():
            logger.info("accounts_file_changed_reloading")
            self.load()
            return True
        return False

    def get_status(self) -> dict[str, Any]:
        """Get pool status for monitoring.

        Returns:
            Status dictionary with counts and account details
        """
        self._check_rate_limit_resets()

        # Find next account that would be selected
        # We need to peek at the cycle without consuming it, so we iterate through account_order
        next_account = None
        if self._account_order:
            for account_name in self._account_order:
                account = self._accounts.get(account_name)
                if account and account.is_available:
                    next_account = account_name
                    break

        return {
            "totalAccounts": self.account_count,
            "availableAccounts": self.available_count,
            "rateLimitedAccounts": self.rate_limited_count,
            "authErrorAccounts": self.auth_error_count,
            "nextAccount": next_account,
            "accounts": [
                self._get_account_status(account) for account in self._accounts.values()
            ],
        }

    def _get_account_status(self, account: Account) -> dict[str, Any]:
        """Get status for a single account."""
        return {
            "name": account.name,
            "state": account.state,
            "tokenExpiresAt": account.credentials.expires_at_datetime.isoformat(),
            "tokenExpiresIn": account.credentials.expires_in_seconds,
            "rateLimitedUntil": (
                datetime.fromtimestamp(
                    account.rate_limited_until / 1000, tz=UTC
                ).isoformat()
                if account.rate_limited_until
                else None
            ),
            "lastUsed": (
                datetime.fromtimestamp(account.last_used / 1000, tz=UTC).isoformat()
                if account.last_used
                else None
            ),
            "lastError": account.last_error,
            # Capacity info
            "tokensLimit": account.tokens_limit,
            "tokensRemaining": account.tokens_remaining,
            "tokensRemainingPercent": account.tokens_remaining_percent,
            "requestsLimit": account.requests_limit,
            "requestsRemaining": account.requests_remaining,
            "requestsRemainingPercent": account.requests_remaining_percent,
            "capacityCheckedAt": (
                datetime.fromtimestamp(
                    account.capacity_checked_at / 1000, tz=UTC
                ).isoformat()
                if account.capacity_checked_at
                else None
            ),
        }


# Global pool instance (initialized by middleware/startup)
_pool: RotationPool | None = None


def get_rotation_pool() -> RotationPool:
    """Get the global rotation pool instance.

    Returns:
        RotationPool instance

    Raises:
        RuntimeError: If pool not initialized
    """
    if _pool is None:
        raise RuntimeError(
            "Rotation pool not initialized. "
            "Ensure rotation middleware is enabled and accounts.json exists."
        )
    return _pool


def init_rotation_pool(accounts_path: Path | None = None) -> RotationPool:
    """Initialize the global rotation pool.

    Args:
        accounts_path: Optional path to accounts.json

    Returns:
        Initialized RotationPool
    """
    global _pool
    _pool = RotationPool(accounts_path=accounts_path)
    return _pool
