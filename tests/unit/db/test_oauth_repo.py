"""Tests for OAuthFlowRepository."""

import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from claude_code_proxy.db import init_db
from claude_code_proxy.db.repositories import OAuthFlowRepository


@pytest.fixture
async def repo():
    """Create repository with temporary database."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        await init_db(db_path)
        yield OAuthFlowRepository()


@pytest.mark.asyncio
async def test_create_flow(repo):
    """Test creating an OAuth flow."""
    before_create = datetime.now(UTC)
    flow = await repo.create(
        state="verifier_123",
        account_name="test-account",
        code_challenge="challenge_abc",
        redirect_uri="http://localhost/callback",
        ttl_seconds=3600,
    )
    assert flow.state == "verifier_123"
    assert flow.account_name == "test-account"
    assert flow.code_challenge == "challenge_abc"
    assert flow.redirect_uri == "http://localhost/callback"
    # Check expires_at is approximately 1 hour in the future
    # (handle both naive and aware datetimes from DB)
    expires_at = flow.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    assert expires_at > before_create
    assert expires_at > before_create + timedelta(minutes=59)


@pytest.mark.asyncio
async def test_get_valid_flow(repo):
    """Test retrieving a valid (non-expired) flow."""
    await repo.create(
        state="valid_state",
        account_name="test",
        code_challenge="challenge",
        redirect_uri="http://localhost/callback",
        ttl_seconds=3600,
    )

    flow = await repo.get_valid("valid_state")
    assert flow is not None
    assert flow.state == "valid_state"


@pytest.mark.asyncio
async def test_get_nonexistent_flow(repo):
    """Test retrieving a nonexistent flow returns None."""
    flow = await repo.get_valid("nonexistent_state")
    assert flow is None


@pytest.mark.asyncio
async def test_get_expired_flow_returns_none(repo):
    """Test that expired flows return None."""
    # Create with negative TTL (already expired)
    await repo.create(
        state="expired_state",
        account_name="test",
        code_challenge="challenge",
        redirect_uri="http://localhost/callback",
        ttl_seconds=-1,  # Already expired
    )

    flow = await repo.get_valid("expired_state")
    assert flow is None


@pytest.mark.asyncio
async def test_delete_flow(repo):
    """Test deleting a flow."""
    await repo.create("to_delete", "test", "ch", "http://localhost", 3600)

    deleted = await repo.delete("to_delete")
    assert deleted is True

    flow = await repo.get_valid("to_delete")
    assert flow is None


@pytest.mark.asyncio
async def test_delete_nonexistent_flow(repo):
    """Test deleting a nonexistent flow returns False."""
    deleted = await repo.delete("nonexistent")
    assert deleted is False


@pytest.mark.asyncio
async def test_cleanup_expired(repo):
    """Test cleanup of expired flows."""
    # Create expired flows
    await repo.create("expired1", "test", "ch", "http://localhost", -100)
    await repo.create("expired2", "test", "ch", "http://localhost", -100)
    # Create valid flow
    await repo.create("valid", "test", "ch", "http://localhost", 3600)

    count = await repo.cleanup_expired()
    assert count == 2

    # Valid flow should still exist
    flow = await repo.get_valid("valid")
    assert flow is not None


@pytest.mark.asyncio
async def test_get_pending_account_names(repo):
    """Test getting list of account names with pending flows."""
    await repo.create("state1", "account-one", "ch", "http://localhost", 3600)
    await repo.create("state2", "account-two", "ch", "http://localhost", 3600)
    await repo.create(
        "state3", "account-one", "ch", "http://localhost", 3600
    )  # Duplicate
    # Create expired flow - should not be included
    await repo.create("expired", "account-three", "ch", "http://localhost", -100)

    names = await repo.get_pending_account_names()
    # account-one appears twice, account-two once, account-three is expired
    assert "account-one" in names
    assert "account-two" in names
    assert "account-three" not in names
