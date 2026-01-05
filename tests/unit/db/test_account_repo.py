"""Tests for AccountRepository."""

import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from claude_code_proxy.db import get_session, init_db
from claude_code_proxy.db.repositories import AccountRepository


@pytest.fixture
async def repo():
    """Create repository with temporary database."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        await init_db(db_path)
        yield AccountRepository()


@pytest.mark.asyncio
async def test_create_account(repo):
    """Test creating an account via repository."""
    account = await repo.create(
        name="new-account",
        access_token="access_token",
        refresh_token="refresh_token",
        expires_at=datetime.now(UTC) + timedelta(hours=24),
    )
    assert account.name == "new-account"


@pytest.mark.asyncio
async def test_get_account(repo):
    """Test retrieving an account."""
    await repo.create(
        name="get-test",
        access_token="access",
        refresh_token="refresh",
        expires_at=datetime.now(UTC) + timedelta(hours=24),
    )

    account = await repo.get("get-test")
    assert account is not None
    assert account.name == "get-test"


@pytest.mark.asyncio
async def test_get_nonexistent_account(repo):
    """Test retrieving nonexistent account returns None."""
    account = await repo.get("does-not-exist")
    assert account is None


@pytest.mark.asyncio
async def test_list_all_accounts(repo):
    """Test listing all accounts."""
    await repo.create("account-1", "a1", "r1", datetime.now(UTC) + timedelta(hours=24))
    await repo.create("account-2", "a2", "r2", datetime.now(UTC) + timedelta(hours=24))

    accounts = await repo.list_all()
    assert len(accounts) == 2
    names = {a.name for a in accounts}
    assert names == {"account-1", "account-2"}


@pytest.mark.asyncio
async def test_delete_account(repo):
    """Test deleting an account."""
    await repo.create("to-delete", "a", "r", datetime.now(UTC) + timedelta(hours=24))

    deleted = await repo.delete("to-delete")
    assert deleted is True

    account = await repo.get("to-delete")
    assert account is None


@pytest.mark.asyncio
async def test_delete_nonexistent_account(repo):
    """Test deleting nonexistent account returns False."""
    deleted = await repo.delete("does-not-exist")
    assert deleted is False


@pytest.mark.asyncio
async def test_update_tokens(repo):
    """Test updating account tokens."""
    await repo.create(
        "update-test",
        "old_access",
        "old_refresh",
        datetime.now(UTC) + timedelta(hours=1),
    )

    new_expires = datetime.now(UTC) + timedelta(hours=24)
    account = await repo.update_tokens(
        "update-test", "new_access", "new_refresh", new_expires
    )

    assert account.access_token == "new_access"
    assert account.refresh_token == "new_refresh"


@pytest.mark.asyncio
async def test_update_tokens_nonexistent(repo):
    """Test updating tokens for nonexistent account returns None."""
    result = await repo.update_tokens(
        "nonexistent", "access", "refresh", datetime.now(UTC) + timedelta(hours=24)
    )
    assert result is None


@pytest.mark.asyncio
async def test_mark_used(repo):
    """Test marking an account as used."""
    await repo.create(
        "mark-test", "access", "refresh", datetime.now(UTC) + timedelta(hours=24)
    )

    # Mark as used
    await repo.mark_used("mark-test")

    # Verify the account was updated
    account = await repo.get("mark-test")
    assert account is not None
    assert account.last_used_at is not None
    assert account.use_count == 1

    # Mark again
    await repo.mark_used("mark-test")
    account = await repo.get("mark-test")
    assert account.use_count == 2


@pytest.mark.asyncio
async def test_create_with_optional_fields(repo):
    """Test creating an account with optional email and display_name."""
    account = await repo.create(
        name="optional-test",
        access_token="access",
        refresh_token="refresh",
        expires_at=datetime.now(UTC) + timedelta(hours=24),
        email="test@example.com",
        display_name="Test User",
    )
    assert account.email == "test@example.com"
    assert account.display_name == "Test User"
