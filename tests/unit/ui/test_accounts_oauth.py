"""Tests for OAuth flow integration in accounts.py with SQLite repository."""

import tempfile
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from claude_code_proxy.db import init_db
from claude_code_proxy.db.repositories import OAuthFlowRepository


@pytest.fixture
async def db_initialized():
    """Initialize a temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        await init_db(db_path)
        yield db_path


@pytest.fixture
async def oauth_repo(db_initialized):
    """Create OAuthFlowRepository with initialized database."""
    return OAuthFlowRepository()


@pytest.mark.asyncio
async def test_oauth_flow_cleanup_expired(oauth_repo):
    """Test that cleanup_expired removes old flows."""
    # Create expired flow
    await oauth_repo.create(
        state="expired_state",
        account_name="test-account",
        code_challenge="challenge",
        redirect_uri="http://localhost/callback",
        ttl_seconds=-100,  # Already expired
    )
    # Create valid flow
    await oauth_repo.create(
        state="valid_state",
        account_name="test-account",
        code_challenge="challenge",
        redirect_uri="http://localhost/callback",
        ttl_seconds=3600,
    )

    count = await oauth_repo.cleanup_expired()
    assert count == 1

    # Valid flow should still exist
    flow = await oauth_repo.get_valid("valid_state")
    assert flow is not None


@pytest.mark.asyncio
async def test_oauth_flow_get_pending_account_names(oauth_repo):
    """Test getting pending account names from repository."""
    await oauth_repo.create(
        state="state1",
        account_name="account-one",
        code_challenge="ch",
        redirect_uri="http://localhost",
        ttl_seconds=3600,
    )
    await oauth_repo.create(
        state="state2",
        account_name="account-two",
        code_challenge="ch",
        redirect_uri="http://localhost",
        ttl_seconds=3600,
    )
    # Expired flow - should not be included
    await oauth_repo.create(
        state="state3",
        account_name="account-three",
        code_challenge="ch",
        redirect_uri="http://localhost",
        ttl_seconds=-100,
    )

    names = await oauth_repo.get_pending_account_names()
    assert "account-one" in names
    assert "account-two" in names
    assert "account-three" not in names


@pytest.mark.asyncio
async def test_oauth_flow_create_and_get(oauth_repo):
    """Test creating and retrieving an OAuth flow via repository."""
    flow = await oauth_repo.create(
        state="test_verifier",
        account_name="my-account",
        code_challenge="my_challenge",
        redirect_uri="http://localhost:8080/callback",
        ttl_seconds=3600,
    )

    assert flow.state == "test_verifier"
    assert flow.account_name == "my-account"
    assert flow.code_challenge == "my_challenge"

    # Retrieve it
    retrieved = await oauth_repo.get_valid("test_verifier")
    assert retrieved is not None
    assert retrieved.account_name == "my-account"


@pytest.mark.asyncio
async def test_oauth_flow_delete_on_complete(oauth_repo):
    """Test that flows are deleted after completion."""
    await oauth_repo.create(
        state="to_complete",
        account_name="completing-account",
        code_challenge="ch",
        redirect_uri="http://localhost",
        ttl_seconds=3600,
    )

    # Verify it exists
    flow = await oauth_repo.get_valid("to_complete")
    assert flow is not None

    # Delete after completion
    deleted = await oauth_repo.delete("to_complete")
    assert deleted is True

    # Should no longer exist
    flow = await oauth_repo.get_valid("to_complete")
    assert flow is None


@pytest.mark.asyncio
async def test_oauth_flow_expired_returns_none(oauth_repo):
    """Test that expired flows return None on get_valid."""
    await oauth_repo.create(
        state="expired_flow",
        account_name="test",
        code_challenge="ch",
        redirect_uri="http://localhost",
        ttl_seconds=-1,  # Expired immediately
    )

    flow = await oauth_repo.get_valid("expired_flow")
    assert flow is None


@pytest.mark.asyncio
async def test_oauth_flow_delete_nonexistent(oauth_repo):
    """Test that deleting a nonexistent flow returns False."""
    deleted = await oauth_repo.delete("does_not_exist")
    assert deleted is False
