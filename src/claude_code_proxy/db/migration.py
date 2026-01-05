"""Migration utilities for transitioning from JSON to SQLite."""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import structlog

from claude_code_proxy.db.repositories import AccountRepository


logger = structlog.get_logger()


async def migrate_from_accounts_json(json_path: Path) -> int:
    """Migrate accounts from accounts.json to SQLite.

    Args:
        json_path: Path to accounts.json file

    Returns:
        Number of accounts migrated (skips existing)
    """
    if not json_path.exists():
        logger.info("migration_skipped_no_file", path=str(json_path))
        return 0

    try:
        data = json.loads(json_path.read_text())
    except (json.JSONDecodeError, OSError):
        logger.exception("migration_failed_read", path=str(json_path))
        return 0

    accounts_dict: dict[str, Any] = data.get("accounts", {})
    if not accounts_dict:
        logger.info("migration_skipped_empty", path=str(json_path))
        return 0

    repo = AccountRepository()
    migrated = 0

    for name, account_data in accounts_dict.items():
        # Check if already exists
        existing = await repo.get(name)
        if existing:
            logger.debug("migration_skipped_exists", account=name)
            continue

        # Parse expiry - handle both Unix timestamp (ms) and ISO8601 formats
        expires_at_value = account_data.get("expiresAt", "")
        try:
            if isinstance(expires_at_value, int):
                # Unix timestamp in milliseconds
                expires_at = datetime.fromtimestamp(expires_at_value / 1000, tz=UTC)
            elif isinstance(expires_at_value, str) and expires_at_value.isdigit():
                # Unix timestamp as string (milliseconds)
                expires_at = datetime.fromtimestamp(
                    int(expires_at_value) / 1000, tz=UTC
                )
            elif isinstance(expires_at_value, str):
                # ISO8601 format - replace Z suffix with +00:00 for proper parsing
                expires_at = datetime.fromisoformat(
                    expires_at_value.replace("Z", "+00:00")
                )
            else:
                raise ValueError(f"Unsupported expiry format: {type(expires_at_value)}")
        except (ValueError, AttributeError, TypeError, OSError) as e:
            logger.warning(
                "migration_invalid_expiry",
                account=name,
                value=expires_at_value,
                error=str(e),
            )
            expires_at = datetime.now(UTC)  # Default to now if invalid

        # Create account
        try:
            await repo.create(
                name=name,
                access_token=account_data.get("accessToken", ""),
                refresh_token=account_data.get("refreshToken", ""),
                expires_at=expires_at,
                email=account_data.get("email"),
                display_name=account_data.get("displayName"),
            )
            migrated += 1
            logger.info("migration_account_created", account=name)
        except Exception:
            logger.exception("migration_account_failed", account=name)

    logger.info("migration_complete", migrated=migrated, total=len(accounts_dict))
    return migrated
