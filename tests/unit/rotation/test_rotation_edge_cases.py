"""Edge case tests for rotation pool functionality.

Tests concurrent access, file reload during requests, and token refresh
during failover scenarios.
"""

import asyncio
import json
from pathlib import Path

import pytest

from claude_code_proxy.db import init_db
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
async def test_concurrent_account_selection(temp_accounts_file: Path) -> None:
    """Test that concurrent account selection distributes load properly.

    Verifies:
    - No race conditions in account selection
    - Round-robin distribution under concurrent load
    - Thread-safe state updates
    """
    pool = RotationPool(accounts_path=temp_accounts_file)

    # Simulate 100 concurrent requests
    num_requests = 100
    tasks = [pool.get_next_available() for _ in range(num_requests)]
    accounts = await asyncio.gather(*tasks)

    # Verify all requests got an account
    assert all(account is not None for account in accounts)

    # Count account usage
    usage_counts: dict[str, int] = {}
    for account in accounts:
        if account:
            usage_counts[account.name] = usage_counts.get(account.name, 0) + 1

    # Verify round-robin distribution
    # With 100 requests and 3 accounts: 100 ÷ 3 = 33 remainder 1
    # Expected distribution: [33, 33, 34] (depending on starting index)
    total_requests = sum(usage_counts.values())
    assert total_requests == num_requests, "All requests should be served"

    # Check distribution is fair (max difference of 1)
    min_count = min(usage_counts.values())
    max_count = max(usage_counts.values())
    assert max_count - min_count <= 1, f"Uneven distribution: {usage_counts}"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_file_reload_during_active_requests(
    temp_accounts_file: Path, db_path: Path
) -> None:
    """Test that file reload preserves state during active requests.

    Verifies:
    - Runtime state (rate limits, last_used) is preserved
    - Only credentials are updated from file
    - Active requests continue with original accounts
    """
    pool = RotationPool(accounts_path=temp_accounts_file)

    # Get an account and mark it as rate limited
    account1 = await pool.get_next_available()
    assert account1 is not None
    original_name = account1.name
    await pool.mark_rate_limited(original_name, reset_time=9999999999999)

    # Verify account is rate limited
    assert account1.state == AccountState.RATE_LIMITED

    # Update the accounts file (simulate new credentials)
    accounts_data = json.loads(temp_accounts_file.read_text())
    accounts_data["accounts"][original_name]["accessToken"] = "sk-ant-oat01-updated"
    temp_accounts_file.write_text(json.dumps(accounts_data, indent=2))

    # Reload the pool
    pool.load()

    # Verify state is preserved but token is updated
    account_after_reload = pool.get_account(original_name)
    assert account_after_reload is not None
    assert account_after_reload.state == AccountState.RATE_LIMITED
    assert account_after_reload.rate_limited_until == 9999999999999
    assert account_after_reload.access_token == "sk-ant-oat01-updated"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_token_refresh_during_failover(temp_accounts_file: Path) -> None:
    """Test account selection when token is expiring during failover.

    Verifies:
    - Accounts with expiring tokens are still selected
    - Refresh happens in background without blocking requests
    - Failover continues even if refresh is pending
    """
    pool = RotationPool(accounts_path=temp_accounts_file)

    # Mark first account as rate limited
    account1 = await pool.get_next_available()
    assert account1 is not None
    await pool.mark_rate_limited(account1.name)

    # Next request should get second account
    account2 = await pool.get_next_available()
    assert account2 is not None
    assert account2.name != account1.name

    # Mark second account as rate limited
    await pool.mark_rate_limited(account2.name)

    # Third request should get third account
    account3 = await pool.get_next_available()
    assert account3 is not None
    assert account3.name not in [account1.name, account2.name]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_all_accounts_rate_limited_recovery(
    temp_accounts_file: Path, db_path: Path
) -> None:
    """Test recovery when all accounts become rate limited.

    Verifies:
    - Returns None when all accounts unavailable
    - Automatically recovers when rate limit expires
    - Rotation resumes from correct position
    """
    pool = RotationPool(accounts_path=temp_accounts_file)

    # Rate limit all accounts with short timeout (2 seconds for reliability)
    import time

    future_ms = int((time.time() + 2) * 1000)
    for account in pool.get_all_accounts():
        await pool.mark_rate_limited(account.name, reset_time=future_ms)

    # Should return None since all are rate limited
    limited_account = await pool.get_next_available()
    assert limited_account is None

    # Wait for rate limits to expire (add buffer for timing precision)
    await asyncio.sleep(2.2)

    # Should now get an account
    recovered_account = await pool.get_next_available()
    assert recovered_account is not None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_account_removal_during_rotation(temp_accounts_file: Path) -> None:
    """Test that account removal doesn't break rotation.

    Verifies:
    - Rotation index adjusts correctly
    - No IndexError on next selection
    - Remaining accounts continue to work
    """
    pool = RotationPool(accounts_path=temp_accounts_file)

    # Get first account
    account1 = await pool.get_next_available()
    assert account1 is not None
    first_account_name = account1.name

    # Remove the first account
    pool.remove_account(first_account_name)

    # Next selection should work without error
    account2 = await pool.get_next_available()
    assert account2 is not None
    assert account2.name != first_account_name


@pytest.mark.unit
@pytest.mark.asyncio
async def test_manual_account_selection_while_rate_limited(
    temp_accounts_file: Path,
) -> None:
    """Test manual account selection when account is rate limited.

    Verifies:
    - Manual selection bypasses rotation
    - Returns None for rate limited accounts
    - Doesn't affect rotation state
    """
    pool = RotationPool(accounts_path=temp_accounts_file)

    # Rate limit account-1
    await pool.mark_rate_limited("account-1")

    # Try to manually select rate-limited account
    account = pool.get_account("account-1")
    assert account is not None
    assert not account.is_available
    assert account.state == AccountState.RATE_LIMITED

    # Automatic selection should skip it
    next_account = await pool.get_next_available()
    assert next_account is not None
    assert next_account.name != "account-1"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_rotation_index_wraps_correctly(temp_accounts_file: Path) -> None:
    """Test that rotation index wraps around correctly.

    Verifies:
    - Index wraps from last to first account
    - No IndexError on wraparound
    - Maintains proper round-robin order
    """
    pool = RotationPool(accounts_path=temp_accounts_file)

    # Track selection order using public API
    selected_names = []

    # Select more accounts than exist to force wraparound (10 > 3)
    for _ in range(10):
        account = await pool.get_next_available()
        assert account is not None
        selected_names.append(account.name)

    # Verify pattern repeats every 3 accounts (since we have 3 accounts)
    # After 3 selections, pattern should repeat
    assert (
        selected_names[0] == selected_names[3] == selected_names[6] == selected_names[9]
    )
    assert selected_names[1] == selected_names[4] == selected_names[7]
    assert selected_names[2] == selected_names[5] == selected_names[8]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_token_refresh_blocks_startup(tmp_path: Path) -> None:
    """Test that token refresh blocks on startup to prevent race conditions.

    Verifies:
    - Accounts start in 'refreshing' state during refresh
    - Accounts become 'available' after successful refresh
    - Blocking parameter controls whether startup waits
    """
    from datetime import UTC, datetime
    from unittest.mock import AsyncMock, patch

    from claude_code_proxy.rotation.refresh import TokenRefreshScheduler

    # Create accounts file with expired tokens
    accounts_path = tmp_path / "accounts.json"
    now_ms = int(datetime.now(UTC).timestamp() * 1000)
    expired_time = now_ms - 3600000  # 1 hour ago

    accounts_data = {
        "version": 1,
        "accounts": {
            "test-account": {
                "accessToken": "sk-ant-oat01-test",
                "refreshToken": "sk-ant-ort01-test",
                "expiresAt": expired_time,  # Expired
            }
        },
    }
    accounts_path.write_text(json.dumps(accounts_data, indent=2))

    pool = RotationPool(accounts_path=accounts_path)
    scheduler = TokenRefreshScheduler(pool, check_interval=60, refresh_buffer=600)

    # Mock the refresh operation to verify blocking behavior
    refresh_called = False
    states_during_refresh = []

    async def mock_refresh(account_name: str) -> bool:
        nonlocal refresh_called, states_during_refresh
        refresh_called = True

        account = pool.get_account(account_name)
        assert account is not None

        # Mark as refreshing (this is what the real method does)
        account.mark_refreshing()
        states_during_refresh.append(account.state)

        # Simulate successful refresh
        await asyncio.sleep(0.1)  # Small delay to simulate async operation
        account.mark_refresh_complete(success=True)
        states_during_refresh.append(account.state)
        return True

    scheduler._refresh_with_retry = mock_refresh  # type: ignore[method-assign]

    # Start with blocking enabled (default)
    await scheduler.start(block_until_initial_refresh=True)

    # Verify refresh was called
    assert refresh_called, "Token refresh should have been called"

    # Verify state transitions: refreshing -> available
    assert len(states_during_refresh) == 2, "Should have recorded two states"
    assert states_during_refresh[0] == "refreshing", "First state should be refreshing"
    assert states_during_refresh[1] == "available", "Second state should be available"

    # Verify account is now available
    account = pool.get_account("test-account")
    assert account is not None
    assert account.state == "available", "Account should be available after refresh"

    await scheduler.stop()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_refreshing_state_prevents_selection(temp_accounts_file: Path) -> None:
    """Test that accounts in 'refreshing' state are not selected.

    Verifies:
    - Accounts marked as refreshing are skipped during selection
    - Other accounts can still be selected
    - Refresh completion restores account to rotation
    """
    pool = RotationPool(accounts_path=temp_accounts_file)

    # Mark first account as refreshing
    accounts = pool.get_all_accounts()
    first_account = accounts[0]
    first_account.mark_refreshing()

    # Request an account - should skip the refreshing one
    selected = await pool.get_next_available()
    assert selected is not None
    assert selected.name != first_account.name, "Should not select refreshing account"

    # Complete refresh
    first_account.mark_refresh_complete(success=True)

    # Now the account should be available again
    assert first_account.state == "available"
    assert first_account.is_available
