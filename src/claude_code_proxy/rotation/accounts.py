"""Account model and file operations for multi-account rotation.

Handles loading, validating, and persisting accounts from ~/.claude/accounts.json.
"""

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import orjson
from structlog import get_logger

from claude_code_proxy.rotation.constants import ONE_HOUR_MILLISECONDS


logger = get_logger(__name__)

# Token validation patterns
ACCESS_TOKEN_PATTERN = re.compile(r"^sk-ant-oat01-[A-Za-z0-9_-]+$")
REFRESH_TOKEN_PATTERN = re.compile(r"^sk-ant-ort01-[A-Za-z0-9_-]+$")
ACCOUNT_NAME_PATTERN = re.compile(r"^[a-z0-9_-]+$")

# Default accounts file path
DEFAULT_ACCOUNTS_PATH = Path("~/.claude/accounts.json").expanduser()


@dataclass
class AccountCredentials:
    """OAuth credentials for a Claude account."""

    access_token: str
    refresh_token: str
    expires_at: int  # Unix timestamp in milliseconds

    @property
    def expires_at_datetime(self) -> datetime:
        """Convert expires_at to datetime."""
        return datetime.fromtimestamp(self.expires_at / 1000, tz=UTC)

    @property
    def is_expired(self) -> bool:
        """Check if the access token is expired."""
        return datetime.now(UTC) >= self.expires_at_datetime

    @property
    def expires_in_seconds(self) -> int:
        """Seconds until token expires (negative if expired)."""
        delta = self.expires_at_datetime - datetime.now(UTC)
        return int(delta.total_seconds())

    def needs_refresh(self, buffer_seconds: int = 600) -> bool:
        """Check if token needs refresh (within buffer of expiration).

        Args:
            buffer_seconds: Refresh if expiring within this many seconds (default 10 min)

        Returns:
            True if token should be refreshed
        """
        return self.expires_in_seconds < buffer_seconds

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "accessToken": self.access_token,
            "refreshToken": self.refresh_token,
            "expiresAt": self.expires_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AccountCredentials":
        """Create from dictionary."""
        return cls(
            access_token=data["accessToken"],
            refresh_token=data["refreshToken"],
            expires_at=data["expiresAt"],
        )


@dataclass
class Account:
    """A Claude account in the rotation pool.

    Combines credentials with runtime state tracking.
    """

    name: str
    credentials: AccountCredentials

    # Runtime state (not persisted to file)
    state: str = "available"  # available, rate_limited, auth_error, disabled
    rate_limited_until: int | None = None  # Unix timestamp ms when rate limit resets
    last_used: int | None = None  # Unix timestamp ms of last request
    last_error: str | None = None  # Most recent error message

    # Capacity info (from last API call - not persisted)
    tokens_limit: int | None = None
    tokens_remaining: int | None = None
    tokens_remaining_percent: float | None = None
    requests_limit: int | None = None
    requests_remaining: int | None = None
    requests_remaining_percent: float | None = None
    capacity_checked_at: int | None = None  # Unix timestamp ms

    def __post_init__(self) -> None:
        """Validate account after initialization."""
        self._validate()

    def _validate(self) -> None:
        """Validate account fields."""
        if not ACCOUNT_NAME_PATTERN.match(self.name):
            raise ValueError(
                f"Invalid account name '{self.name}': "
                "must be lowercase alphanumeric with underscores/hyphens"
            )
        if len(self.name) > 32:
            raise ValueError(f"Account name '{self.name}' too long: max 32 characters")

    @property
    def access_token(self) -> str:
        """Get the access token."""
        return self.credentials.access_token

    @property
    def refresh_token(self) -> str:
        """Get the refresh token."""
        return self.credentials.refresh_token

    @property
    def is_available(self) -> bool:
        """Check if account is available for requests."""
        if self.state != "available":
            return False
        return not self.credentials.is_expired

    def mark_rate_limited(self, reset_time: int | None = None) -> None:
        """Mark account as rate limited.

        Args:
            reset_time: Unix timestamp (ms) when rate limit resets.
                       If None, defaults to 1 hour from now.
        """
        self.state = "rate_limited"
        if reset_time is None:
            # Default to 1 hour from now
            reset_time = (
                int(datetime.now(UTC).timestamp() * 1000) + ONE_HOUR_MILLISECONDS
            )
        self.rate_limited_until = reset_time
        logger.info(
            "account_rate_limited",
            account=self.name,
            reset_time=datetime.fromtimestamp(reset_time / 1000, tz=UTC).isoformat(),
        )

    def mark_auth_error(self, error: str) -> None:
        """Mark account as having authentication error.

        Args:
            error: Error message describing the auth failure
        """
        self.state = "auth_error"
        self.last_error = error
        logger.error("account_auth_error", account=self.name, error=error)

    def mark_available(self) -> None:
        """Mark account as available (reset from rate_limited or auth_error)."""
        old_state = self.state
        self.state = "available"
        self.rate_limited_until = None
        self.last_error = None
        logger.info("account_available", account=self.name, previous_state=old_state)

    def mark_used(self) -> None:
        """Record that this account was used for a request."""
        self.last_used = int(datetime.now(UTC).timestamp() * 1000)

    def check_rate_limit_reset(self) -> bool:
        """Check if rate limit has reset and restore availability.

        Returns:
            True if account was restored to available
        """
        if self.state != "rate_limited":
            return False

        if self.rate_limited_until is None:
            return False

        now_ms = int(datetime.now(UTC).timestamp() * 1000)
        if now_ms >= self.rate_limited_until:
            self.mark_available()
            return True

        return False

    def update_credentials(self, new_credentials: AccountCredentials) -> None:
        """Update account credentials (e.g., after token refresh).

        Args:
            new_credentials: New credentials to use
        """
        self.credentials = new_credentials
        logger.debug("account_credentials_updated", account=self.name)

    def update_capacity(
        self,
        tokens_limit: int | None = None,
        tokens_remaining: int | None = None,
        requests_limit: int | None = None,
        requests_remaining: int | None = None,
    ) -> None:
        """Update capacity info from rate limit headers.

        Args:
            tokens_limit: Max tokens per period
            tokens_remaining: Remaining tokens this period
            requests_limit: Max requests per period
            requests_remaining: Remaining requests this period
        """
        self.tokens_limit = tokens_limit
        self.tokens_remaining = tokens_remaining
        self.requests_limit = requests_limit
        self.requests_remaining = requests_remaining

        # Calculate percentages
        if tokens_limit and tokens_remaining is not None:
            self.tokens_remaining_percent = (tokens_remaining / tokens_limit) * 100
        else:
            self.tokens_remaining_percent = None

        if requests_limit and requests_remaining is not None:
            self.requests_remaining_percent = (
                requests_remaining / requests_limit
            ) * 100
        else:
            self.requests_remaining_percent = None

        self.capacity_checked_at = int(datetime.now(UTC).timestamp() * 1000)
        logger.debug(
            "account_capacity_updated",
            account=self.name,
            tokens_pct=self.tokens_remaining_percent,
            requests_pct=self.requests_remaining_percent,
        )


@dataclass
class AccountsFile:
    """Represents the accounts.json file structure."""

    version: int
    accounts: dict[str, Account] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization.

        Note: Only credentials are persisted, not runtime state.
        """
        return {
            "version": self.version,
            "accounts": {
                name: account.credentials.to_dict()
                for name, account in self.accounts.items()
            },
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AccountsFile":
        """Create from dictionary loaded from JSON."""
        version = data.get("version", 1)
        accounts_data = data.get("accounts", {})

        accounts = {}
        for name, cred_data in accounts_data.items():
            try:
                credentials = AccountCredentials.from_dict(cred_data)
                accounts[name] = Account(name=name, credentials=credentials)
            except (KeyError, ValueError) as e:
                logger.warning(
                    "invalid_account_skipped",
                    account=name,
                    error=str(e),
                )

        return cls(version=version, accounts=accounts)


def validate_token_format(token: str, token_type: str) -> bool:
    """Validate token format.

    Args:
        token: Token string to validate
        token_type: Either "access" or "refresh"

    Returns:
        True if token matches expected format
    """
    if token_type == "access":
        return bool(ACCESS_TOKEN_PATTERN.match(token))
    elif token_type == "refresh":
        return bool(REFRESH_TOKEN_PATTERN.match(token))
    return False


def load_accounts(path: Path | None = None) -> AccountsFile:
    """Load accounts from JSON file.

    Args:
        path: Path to accounts.json. Defaults to ~/.claude/accounts.json

    Returns:
        AccountsFile with loaded accounts

    Raises:
        FileNotFoundError: If file doesn't exist
        json.JSONDecodeError: If file is invalid JSON
        ValueError: If file structure is invalid
    """
    if path is None:
        path = DEFAULT_ACCOUNTS_PATH

    path = Path(path).expanduser()

    if not path.exists():
        raise FileNotFoundError(f"Accounts file not found: {path}")

    logger.debug("loading_accounts", path=str(path))

    with path.open("rb") as f:
        data = orjson.loads(f.read())

    if not isinstance(data, dict):
        raise ValueError(
            f"Invalid accounts file format: expected object, got {type(data)}"
        )

    if "accounts" not in data:
        raise ValueError("Invalid accounts file: missing 'accounts' field")

    accounts_file = AccountsFile.from_dict(data)

    logger.info(
        "accounts_loaded",
        path=str(path),
        count=len(accounts_file.accounts),
        accounts=list(accounts_file.accounts.keys()),
    )

    return accounts_file


def save_accounts(accounts_file: AccountsFile, path: Path | None = None) -> bool:
    """Save accounts to JSON file.

    Args:
        accounts_file: AccountsFile to save
        path: Path to save to. Defaults to ~/.claude/accounts.json

    Returns:
        True if saved successfully
    """
    if path is None:
        path = DEFAULT_ACCOUNTS_PATH

    path = Path(path).expanduser()

    # Ensure directory exists
    path.parent.mkdir(parents=True, exist_ok=True)

    try:
        # Write to temp file first, then rename for atomicity
        temp_path = path.with_suffix(".json.tmp")
        with temp_path.open("wb") as f:
            f.write(orjson.dumps(accounts_file.to_dict(), option=orjson.OPT_INDENT_2))

        temp_path.rename(path)

        logger.debug(
            "accounts_saved",
            path=str(path),
            count=len(accounts_file.accounts),
        )
        return True

    except OSError as e:
        # OSError: File system errors (permissions, disk full, path issues)
        logger.error("accounts_save_failed", path=str(path), error=str(e))
        return False
