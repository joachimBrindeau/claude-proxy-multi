"""Integration tests for SQLite database."""

import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from claude_code_proxy.db import init_db
from claude_code_proxy.db.repositories import (
    AccountRepository,
    OAuthFlowRepository,
    RateLimitRepository,
)


@pytest.fixture
async def temp_db():
    """Create a temporary database for testing."""
    from claude_code_proxy.db import engine as engine_module

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        await init_db(db_path)
        yield db_path

        # Cleanup (runs after test completes)
        if engine_module._engine:
            await engine_module._engine.dispose()  # type: ignore[unreachable]


@pytest.mark.asyncio
async def test_full_account_lifecycle(temp_db):
    """Test complete account CRUD operations."""
    repo = AccountRepository()

    # Create
    account = await repo.create(
        name="test-account",
        access_token="access123",
        refresh_token="refresh456",
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    assert account.name == "test-account"

    # Read
    fetched = await repo.get("test-account")
    assert fetched is not None
    assert fetched.access_token == "access123"

    # Update
    updated = await repo.update_tokens(
        "test-account",
        access_token="new_access",
        refresh_token="new_refresh",
        expires_at=datetime.now(UTC) + timedelta(hours=2),
    )
    assert updated is not None
    assert updated.access_token == "new_access"

    # List
    all_accounts = await repo.list_all()
    assert len(all_accounts) == 1

    # Delete
    deleted = await repo.delete("test-account")
    assert deleted is True
    assert await repo.get("test-account") is None


@pytest.mark.asyncio
async def test_oauth_flow_persistence(temp_db):
    """Test OAuth flow state persists and expires correctly."""
    repo = OAuthFlowRepository()

    # Create flow
    flow = await repo.create(
        state="test-state-123",
        account_name="oauth-account",
        code_challenge="challenge456",
        redirect_uri="http://localhost/callback",
        ttl_seconds=3600,
    )
    assert flow.state == "test-state-123"

    # Retrieve valid flow
    valid = await repo.get_valid("test-state-123")
    assert valid is not None
    assert valid.account_name == "oauth-account"

    # Get pending account names
    pending = await repo.get_pending_account_names()
    assert "oauth-account" in pending

    # Delete flow
    await repo.delete("test-state-123")
    assert await repo.get_valid("test-state-123") is None


@pytest.mark.asyncio
async def test_rate_limit_persistence(temp_db):
    """Test rate limit state persists correctly."""
    account_repo = AccountRepository()
    rate_repo = RateLimitRepository()

    # Need an account first (foreign key)
    await account_repo.create(
        name="rate-test-account",
        access_token="token",
        refresh_token="refresh",
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )

    # Mark as rate limited
    reset_time = datetime.now(UTC) + timedelta(minutes=30)
    await rate_repo.mark_limited("rate-test-account", reset_time)

    # Check is limited
    is_limited = await rate_repo.is_limited("rate-test-account")
    assert is_limited is True

    # Get all limited
    all_limited = await rate_repo.get_all_limited()
    assert len(all_limited) == 1
    assert all_limited[0].account_name == "rate-test-account"

    # Clear
    await rate_repo.clear("rate-test-account")
    assert await rate_repo.is_limited("rate-test-account") is False


@pytest.mark.asyncio
async def test_data_survives_engine_restart(temp_db):
    """Test data persists after closing and reopening the database."""
    from claude_code_proxy.db import engine as engine_module
    from claude_code_proxy.db.engine import get_engine

    repo = AccountRepository()

    # Create account
    await repo.create(
        name="persist-test",
        access_token="access",
        refresh_token="refresh",
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )

    # Dispose engine (simulate restart)
    engine = get_engine()
    await engine.dispose()

    # Reinitialize
    await init_db(temp_db)

    # Data should still exist
    fetched = await repo.get("persist-test")
    assert fetched is not None
    assert fetched.name == "persist-test"


@pytest.mark.asyncio
async def test_all_repositories_work_together(temp_db):
    """Integration test using all repositories together."""
    account_repo = AccountRepository()
    oauth_repo = OAuthFlowRepository()
    rate_repo = RateLimitRepository()

    # Create account
    await account_repo.create(
        name="full-test-account",
        access_token="token",
        refresh_token="refresh",
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )

    # Start OAuth flow for same account name
    await oauth_repo.create(
        state="full-test-state",
        account_name="full-test-account",
        code_challenge="challenge",
        redirect_uri="http://localhost",
        ttl_seconds=600,
    )

    # Rate limit the account
    await rate_repo.mark_limited(
        "full-test-account",
        datetime.now(UTC) + timedelta(minutes=15),
    )

    # Verify all state
    account = await account_repo.get("full-test-account")
    assert account is not None

    flow = await oauth_repo.get_valid("full-test-state")
    assert flow is not None

    is_limited = await rate_repo.is_limited("full-test-account")
    assert is_limited is True

    # Cleanup OAuth flow
    await oauth_repo.delete("full-test-state")

    # Clear rate limit
    await rate_repo.clear("full-test-account")

    # Account still exists
    assert await account_repo.get("full-test-account") is not None
