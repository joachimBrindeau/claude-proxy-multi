"""Tests for RateLimitRepository."""

import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from claude_code_proxy.db import init_db
from claude_code_proxy.db.repositories import AccountRepository, RateLimitRepository


@pytest.fixture
async def repos():
    """Create repositories with temporary database."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        await init_db(db_path)
        # Create test account first (RateLimit has foreign key to Account)
        account_repo = AccountRepository()
        await account_repo.create(
            "test-account",
            "access",
            "refresh",
            datetime.now(UTC) + timedelta(hours=24),
        )
        yield RateLimitRepository(), account_repo


@pytest.mark.asyncio
async def test_mark_rate_limited(repos):
    """Test marking an account as rate limited."""
    rate_repo, _ = repos

    reset_time = datetime.now(UTC) + timedelta(minutes=30)
    rate_limit = await rate_repo.mark_limited(
        account_name="test-account",
        resets_at=reset_time,
        triggered_by="/v1/messages",
    )

    assert rate_limit.account_name == "test-account"
    # SQLite stores naive datetimes, so compare without timezone
    assert rate_limit.resets_at.replace(tzinfo=None) == reset_time.replace(tzinfo=None)
    assert rate_limit.triggered_by == "/v1/messages"


@pytest.mark.asyncio
async def test_mark_limited_upserts(repos):
    """Test that mark_limited updates existing rate limit."""
    rate_repo, _ = repos

    # First rate limit
    reset_time_1 = datetime.now(UTC) + timedelta(minutes=30)
    await rate_repo.mark_limited("test-account", reset_time_1, "/v1/messages")

    # Second rate limit should update, not create new
    reset_time_2 = datetime.now(UTC) + timedelta(minutes=60)
    rate_limit = await rate_repo.mark_limited("test-account", reset_time_2, "/v1/chat")

    # SQLite stores naive datetimes, so compare without timezone
    assert rate_limit.resets_at.replace(tzinfo=None) == reset_time_2.replace(
        tzinfo=None
    )
    assert rate_limit.triggered_by == "/v1/chat"

    # Verify only one record exists
    all_limited = await rate_repo.get_all_limited()
    assert len(all_limited) == 1


@pytest.mark.asyncio
async def test_is_rate_limited(repos):
    """Test checking if account is rate limited."""
    rate_repo, _ = repos

    # Not limited initially
    assert await rate_repo.is_limited("test-account") is False

    # Mark as limited
    await rate_repo.mark_limited(
        "test-account",
        datetime.now(UTC) + timedelta(minutes=30),
    )

    # Now limited
    assert await rate_repo.is_limited("test-account") is True


@pytest.mark.asyncio
async def test_rate_limit_auto_clears(repos):
    """Test that expired rate limits return as not limited."""
    rate_repo, _ = repos

    # Mark as limited with past reset time
    await rate_repo.mark_limited(
        "test-account",
        datetime.now(UTC) - timedelta(minutes=1),  # Already reset
    )

    # Should not be limited (reset time passed)
    assert await rate_repo.is_limited("test-account") is False


@pytest.mark.asyncio
async def test_get_rate_limit(repos):
    """Test getting rate limit info."""
    rate_repo, _ = repos

    # No rate limit initially
    assert await rate_repo.get("test-account") is None

    # Add rate limit
    reset_time = datetime.now(UTC) + timedelta(minutes=30)
    await rate_repo.mark_limited("test-account", reset_time, "/v1/messages")

    # Should retrieve it
    rate_limit = await rate_repo.get("test-account")
    assert rate_limit is not None
    assert rate_limit.account_name == "test-account"
    assert rate_limit.triggered_by == "/v1/messages"


@pytest.mark.asyncio
async def test_clear_rate_limit(repos):
    """Test manually clearing a rate limit."""
    rate_repo, _ = repos

    await rate_repo.mark_limited(
        "test-account",
        datetime.now(UTC) + timedelta(minutes=30),
    )

    cleared = await rate_repo.clear("test-account")
    assert cleared is True

    assert await rate_repo.is_limited("test-account") is False
    assert await rate_repo.get("test-account") is None


@pytest.mark.asyncio
async def test_clear_nonexistent_rate_limit(repos):
    """Test clearing a rate limit that doesn't exist."""
    rate_repo, _ = repos

    cleared = await rate_repo.clear("test-account")
    assert cleared is False


@pytest.mark.asyncio
async def test_get_all_limited(repos):
    """Test getting all rate-limited accounts."""
    rate_repo, account_repo = repos

    # Create another account
    await account_repo.create(
        "account-2",
        "access",
        "refresh",
        datetime.now(UTC) + timedelta(hours=24),
    )

    # Limit both
    await rate_repo.mark_limited(
        "test-account", datetime.now(UTC) + timedelta(minutes=30)
    )
    await rate_repo.mark_limited("account-2", datetime.now(UTC) + timedelta(minutes=15))

    limited = await rate_repo.get_all_limited()
    assert len(limited) == 2
    names = {rl.account_name for rl in limited}
    assert names == {"test-account", "account-2"}


@pytest.mark.asyncio
async def test_get_all_limited_excludes_expired(repos):
    """Test that get_all_limited excludes expired rate limits."""
    rate_repo, account_repo = repos

    # Create another account
    await account_repo.create(
        "account-2",
        "access",
        "refresh",
        datetime.now(UTC) + timedelta(hours=24),
    )

    # One active, one expired
    await rate_repo.mark_limited(
        "test-account", datetime.now(UTC) + timedelta(minutes=30)
    )
    await rate_repo.mark_limited(
        "account-2", datetime.now(UTC) - timedelta(minutes=1)
    )  # Expired

    limited = await rate_repo.get_all_limited()
    assert len(limited) == 1
    assert limited[0].account_name == "test-account"


@pytest.mark.asyncio
async def test_cleanup_expired(repos):
    """Test cleanup of expired rate limits."""
    rate_repo, account_repo = repos

    # Create additional accounts
    await account_repo.create(
        "account-2",
        "access",
        "refresh",
        datetime.now(UTC) + timedelta(hours=24),
    )
    await account_repo.create(
        "account-3",
        "access",
        "refresh",
        datetime.now(UTC) + timedelta(hours=24),
    )

    # Create expired rate limits
    await rate_repo.mark_limited(
        "test-account", datetime.now(UTC) - timedelta(minutes=10)
    )
    await rate_repo.mark_limited("account-2", datetime.now(UTC) - timedelta(minutes=5))
    # One valid rate limit
    await rate_repo.mark_limited("account-3", datetime.now(UTC) + timedelta(minutes=30))

    # Cleanup expired
    count = await rate_repo.cleanup_expired()
    assert count == 2

    # Only valid one should remain
    remaining = await rate_repo.get("account-3")
    assert remaining is not None

    # Expired ones should be gone
    assert await rate_repo.get("test-account") is None
    assert await rate_repo.get("account-2") is None
