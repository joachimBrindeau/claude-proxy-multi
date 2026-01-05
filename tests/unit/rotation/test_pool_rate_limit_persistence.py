"""Tests for rotation pool rate limit persistence to SQLite.

Tests that rate limits are persisted to SQLite and restored on startup,
ensuring rate limits survive restarts.
"""

import asyncio
import json
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from claude_code_proxy.db import init_db
from claude_code_proxy.db.repositories import RateLimitRepository
from claude_code_proxy.rotation.pool import AccountState, RotationPool


@pytest.fixture
def temp_accounts_file(tmp_path: Path) -> Path:
    """Create a temporary accounts file for testing."""
    accounts_path = tmp_path / "accounts.json"
    accounts_data = {
        "version": 1,
        "accounts": {
            "account-1": {
                "accessToken": "sk-ant-oat01-test1",
                "refreshToken": "sk-ant-ort01-test1",
                "expiresAt": 9999999999999,  # Far future
            },
            "account-2": {
                "accessToken": "sk-ant-oat01-test2",
                "refreshToken": "sk-ant-ort01-test2",
                "expiresAt": 9999999999999,
            },
            "account-3": {
                "accessToken": "sk-ant-oat01-test3",
                "refreshToken": "sk-ant-ort01-test3",
                "expiresAt": 9999999999999,
            },
        },
    }
    accounts_path.write_text(json.dumps(accounts_data, indent=2))
    return accounts_path


@pytest.fixture
async def db_path(tmp_path: Path) -> Path:
    """Initialize a temporary test database."""
    db_file = tmp_path / "test.db"
    await init_db(db_file)
    return db_file


@pytest.mark.unit
@pytest.mark.asyncio
async def test_mark_rate_limited_persists_to_db(
    temp_accounts_file: Path, db_path: Path
) -> None:
    """Test that marking an account as rate limited persists to SQLite.

    Verifies:
    - Rate limit is stored in database
    - Reset time is correctly persisted
    """
    pool = RotationPool(accounts_path=temp_accounts_file)

    # Mark account as rate limited with specific reset time
    reset_time_ms = int((datetime.now(UTC) + timedelta(minutes=30)).timestamp() * 1000)
    await pool.mark_rate_limited("account-1", reset_time=reset_time_ms)

    # Verify rate limit was persisted to database
    repo = RateLimitRepository()
    is_limited = await repo.is_limited("account-1")
    assert is_limited is True

    # Verify reset time was correctly stored
    rate_limit = await repo.get("account-1")
    assert rate_limit is not None
    # SQLite returns naive datetimes - treat as UTC
    db_reset = rate_limit.resets_at
    if db_reset.tzinfo is None:
        db_reset = db_reset.replace(tzinfo=UTC)
    # Convert ms to datetime for comparison
    expected_reset = datetime.fromtimestamp(reset_time_ms / 1000, tz=UTC)
    # Allow 1 second tolerance for timing
    assert abs((db_reset - expected_reset).total_seconds()) < 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_load_rate_limits_from_db_restores_state(
    temp_accounts_file: Path, db_path: Path
) -> None:
    """Test that rate limits are restored from database on startup.

    Verifies:
    - Rate limits persist across pool instances
    - State is correctly restored (rate_limited_until, state)
    """
    # Create first pool instance and mark account as rate limited
    pool1 = RotationPool(accounts_path=temp_accounts_file)
    reset_time_ms = int((datetime.now(UTC) + timedelta(minutes=30)).timestamp() * 1000)
    await pool1.mark_rate_limited("account-1", reset_time=reset_time_ms)

    # Simulate restart: create a new pool instance
    pool2 = RotationPool(accounts_path=temp_accounts_file)
    await pool2.load_rate_limits_from_db()

    # Verify rate limit state was restored
    account = pool2.get_account("account-1")
    assert account is not None
    assert account.state == AccountState.RATE_LIMITED
    # Verify reset time is approximately correct (within 5 seconds)
    # There can be small timing differences due to test execution
    assert account.rate_limited_until is not None
    assert abs(account.rate_limited_until - reset_time_ms) < 5000  # 5 second tolerance


@pytest.mark.unit
@pytest.mark.asyncio
async def test_expired_rate_limits_not_restored(
    temp_accounts_file: Path, db_path: Path
) -> None:
    """Test that expired rate limits are not restored from database.

    Verifies:
    - Only currently active (non-expired) rate limits are loaded
    - Accounts with expired rate limits remain available
    """
    # Add an expired rate limit directly to the database
    repo = RateLimitRepository()
    expired_time = datetime.now(UTC) - timedelta(minutes=5)
    await repo.mark_limited("account-1", resets_at=expired_time)

    # Create pool and load rate limits
    pool = RotationPool(accounts_path=temp_accounts_file)
    await pool.load_rate_limits_from_db()

    # Account should be available (expired rate limits not loaded)
    account = pool.get_account("account-1")
    assert account is not None
    assert account.state == AccountState.AVAILABLE


@pytest.mark.unit
@pytest.mark.asyncio
async def test_multiple_rate_limits_restored(
    temp_accounts_file: Path, db_path: Path
) -> None:
    """Test that multiple rate limits are restored correctly.

    Verifies:
    - All rate-limited accounts are restored
    - Each account has correct reset time (within tolerance)
    """
    pool1 = RotationPool(accounts_path=temp_accounts_file)

    # Rate limit multiple accounts with different reset times
    reset_time_1 = int((datetime.now(UTC) + timedelta(minutes=10)).timestamp() * 1000)
    reset_time_2 = int((datetime.now(UTC) + timedelta(minutes=20)).timestamp() * 1000)

    await pool1.mark_rate_limited("account-1", reset_time=reset_time_1)
    await pool1.mark_rate_limited("account-2", reset_time=reset_time_2)

    # Simulate restart
    pool2 = RotationPool(accounts_path=temp_accounts_file)
    await pool2.load_rate_limits_from_db()

    # Verify both accounts have their rate limits restored
    account1 = pool2.get_account("account-1")
    account2 = pool2.get_account("account-2")
    account3 = pool2.get_account("account-3")

    assert account1 is not None
    assert account1.state == AccountState.RATE_LIMITED
    assert account1.rate_limited_until is not None
    # Allow 5 second tolerance for timing differences
    assert abs(account1.rate_limited_until - reset_time_1) < 5000

    assert account2 is not None
    assert account2.state == AccountState.RATE_LIMITED
    assert account2.rate_limited_until is not None
    assert abs(account2.rate_limited_until - reset_time_2) < 5000

    # Account 3 should remain available
    assert account3 is not None
    assert account3.state == AccountState.AVAILABLE


@pytest.mark.unit
@pytest.mark.asyncio
async def test_rate_limit_with_headers_persists(
    temp_accounts_file: Path, db_path: Path
) -> None:
    """Test that rate limits parsed from headers are persisted.

    Verifies:
    - Rate limits set via headers dict are persisted
    - Retry-after parsing works with persistence
    """
    pool = RotationPool(accounts_path=temp_accounts_file)

    # Use retry-after header (seconds from now)
    headers = {"retry-after": "1800"}  # 30 minutes in seconds
    await pool.mark_rate_limited("account-1", headers=headers)

    # Verify rate limit was persisted
    repo = RateLimitRepository()
    is_limited = await repo.is_limited("account-1")
    assert is_limited is True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_unknown_account_rate_limit_not_persisted(
    temp_accounts_file: Path, db_path: Path
) -> None:
    """Test that rate limiting unknown accounts doesn't persist.

    Verifies:
    - Unknown accounts are gracefully handled
    - No database entry is created for unknown accounts
    """
    pool = RotationPool(accounts_path=temp_accounts_file)

    # Try to rate limit an account that doesn't exist
    await pool.mark_rate_limited("nonexistent-account", reset_time=9999999999999)

    # Verify no rate limit was persisted
    repo = RateLimitRepository()
    is_limited = await repo.is_limited("nonexistent-account")
    assert is_limited is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_rate_limit_survives_restart_integration(
    temp_accounts_file: Path, db_path: Path
) -> None:
    """Integration test: rate limits survive simulated restart.

    This is an end-to-end test simulating:
    1. Rate limiting accounts
    2. "Restarting" the application (new pool instance)
    3. Verifying rate limits are restored and affect account selection
    """
    # Phase 1: Rate limit an account
    pool1 = RotationPool(accounts_path=temp_accounts_file)
    reset_time_ms = int((datetime.now(UTC) + timedelta(hours=1)).timestamp() * 1000)
    await pool1.mark_rate_limited("account-1", reset_time=reset_time_ms)

    # Account should not be available
    account1 = await pool1.get_next_available()
    assert account1 is not None
    assert account1.name != "account-1"  # Should skip rate-limited account

    # Phase 2: Simulate restart
    pool2 = RotationPool(accounts_path=temp_accounts_file)
    await pool2.load_rate_limits_from_db()

    # Rate limit should still be in effect
    assert pool2.rate_limited_count == 1

    # Verify account-1 is still skipped in rotation
    # Get accounts multiple times to cycle through
    selected_names = []
    for _ in range(6):  # 2 full cycles of available accounts
        account = await pool2.get_next_available()
        if account:
            selected_names.append(account.name)

    # account-1 should never be selected
    assert "account-1" not in selected_names
    # Only account-2 and account-3 should be selected
    assert set(selected_names) == {"account-2", "account-3"}
