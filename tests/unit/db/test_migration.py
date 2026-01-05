"""Tests for accounts.json to SQLite migration."""

import json
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from claude_code_proxy.db import init_db
from claude_code_proxy.db.migration import migrate_from_accounts_json
from claude_code_proxy.db.repositories import AccountRepository


@pytest.fixture
async def setup():
    """Create temp dirs and init db."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        db_path = tmpdir_path / "proxy.db"
        json_path = tmpdir_path / "accounts.json"

        await init_db(db_path)
        yield tmpdir_path, db_path, json_path


@pytest.mark.asyncio
async def test_migrate_accounts(setup):
    """Test migrating accounts from JSON."""
    tmpdir, db_path, json_path = setup

    # Create accounts.json
    accounts_data = {
        "accounts": {
            "account-one": {
                "accessToken": "access_1",
                "refreshToken": "refresh_1",
                "expiresAt": (datetime.now(UTC) + timedelta(hours=24)).isoformat(),
            },
            "account-two": {
                "accessToken": "access_2",
                "refreshToken": "refresh_2",
                "expiresAt": (datetime.now(UTC) + timedelta(hours=12)).isoformat(),
            },
        }
    }
    json_path.write_text(json.dumps(accounts_data))

    # Run migration
    count = await migrate_from_accounts_json(json_path)
    assert count == 2

    # Verify accounts in DB
    repo = AccountRepository()
    accounts = await repo.list_all()
    assert len(accounts) == 2

    account_one = await repo.get("account-one")
    assert account_one is not None
    assert account_one.access_token == "access_1"


@pytest.mark.asyncio
async def test_migrate_skips_existing(setup):
    """Test that migration doesn't overwrite existing accounts."""
    tmpdir, db_path, json_path = setup

    # Create existing account in DB
    repo = AccountRepository()
    await repo.create(
        "existing",
        "db_access",
        "db_refresh",
        datetime.now(UTC) + timedelta(hours=24),
    )

    # Create accounts.json with same account
    accounts_data = {
        "accounts": {
            "existing": {
                "accessToken": "json_access",
                "refreshToken": "json_refresh",
                "expiresAt": (datetime.now(UTC) + timedelta(hours=24)).isoformat(),
            },
        }
    }
    json_path.write_text(json.dumps(accounts_data))

    # Run migration
    count = await migrate_from_accounts_json(json_path)
    assert count == 0  # Skipped existing

    # Verify original data preserved
    account = await repo.get("existing")
    assert account is not None
    assert account.access_token == "db_access"  # Not overwritten


@pytest.mark.asyncio
async def test_migrate_nonexistent_file(setup):
    """Test migration with nonexistent file does nothing."""
    tmpdir, db_path, json_path = setup

    count = await migrate_from_accounts_json(Path("/nonexistent/accounts.json"))
    assert count == 0


@pytest.mark.asyncio
async def test_migrate_with_z_suffix_datetime(setup):
    """Test migration handles ISO8601 datetime with Z suffix."""
    tmpdir, db_path, json_path = setup

    # Create accounts.json with Z suffix datetime
    accounts_data = {
        "accounts": {
            "z-account": {
                "accessToken": "access_z",
                "refreshToken": "refresh_z",
                "expiresAt": "2025-01-15T10:30:00Z",
            },
        }
    }
    json_path.write_text(json.dumps(accounts_data))

    # Run migration
    count = await migrate_from_accounts_json(json_path)
    assert count == 1

    # Verify account created with correct expiry
    repo = AccountRepository()
    account = await repo.get("z-account")
    assert account is not None
    assert account.token_expires_at is not None


@pytest.mark.asyncio
async def test_migrate_with_optional_fields(setup):
    """Test migration handles optional email and displayName fields."""
    tmpdir, db_path, json_path = setup

    # Create accounts.json with optional fields
    accounts_data = {
        "accounts": {
            "full-account": {
                "accessToken": "access_full",
                "refreshToken": "refresh_full",
                "expiresAt": (datetime.now(UTC) + timedelta(hours=24)).isoformat(),
                "email": "test@example.com",
                "displayName": "Test User",
            },
        }
    }
    json_path.write_text(json.dumps(accounts_data))

    # Run migration
    count = await migrate_from_accounts_json(json_path)
    assert count == 1

    # Verify optional fields migrated
    repo = AccountRepository()
    account = await repo.get("full-account")
    assert account is not None
    assert account.email == "test@example.com"
    assert account.display_name == "Test User"


@pytest.mark.asyncio
async def test_migrate_empty_accounts(setup):
    """Test migration with empty accounts dict."""
    tmpdir, db_path, json_path = setup

    # Create accounts.json with empty accounts
    accounts_data: dict[str, dict[str, dict[str, str]]] = {"accounts": {}}
    json_path.write_text(json.dumps(accounts_data))

    # Run migration
    count = await migrate_from_accounts_json(json_path)
    assert count == 0


@pytest.mark.asyncio
async def test_migrate_invalid_json(setup):
    """Test migration handles invalid JSON gracefully."""
    tmpdir, db_path, json_path = setup

    # Create invalid JSON file
    json_path.write_text("not valid json {{{")

    # Run migration
    count = await migrate_from_accounts_json(json_path)
    assert count == 0


@pytest.mark.asyncio
async def test_migrate_partial_success(setup):
    """Test migration continues after skipping existing accounts."""
    tmpdir, db_path, json_path = setup

    # Create existing account in DB
    repo = AccountRepository()
    await repo.create(
        "existing",
        "db_access",
        "db_refresh",
        datetime.now(UTC) + timedelta(hours=24),
    )

    # Create accounts.json with existing and new accounts
    accounts_data = {
        "accounts": {
            "existing": {
                "accessToken": "json_access",
                "refreshToken": "json_refresh",
                "expiresAt": (datetime.now(UTC) + timedelta(hours=24)).isoformat(),
            },
            "new-account": {
                "accessToken": "new_access",
                "refreshToken": "new_refresh",
                "expiresAt": (datetime.now(UTC) + timedelta(hours=24)).isoformat(),
            },
        }
    }
    json_path.write_text(json.dumps(accounts_data))

    # Run migration
    count = await migrate_from_accounts_json(json_path)
    assert count == 1  # Only new account migrated

    # Verify both accounts exist with correct data
    existing = await repo.get("existing")
    assert existing is not None
    assert existing.access_token == "db_access"  # Not overwritten

    new = await repo.get("new-account")
    assert new is not None
    assert new.access_token == "new_access"


@pytest.mark.asyncio
async def test_migrate_with_unix_timestamp_ms(setup):
    """Test migration handles Unix timestamps in milliseconds (real accounts.json format)."""
    tmpdir, db_path, json_path = setup

    # Use actual Unix timestamp in milliseconds (like real accounts.json)
    # 1767408126076 = Jan 2, 2026 (approximately)
    unix_ts_ms = int((datetime.now(UTC) + timedelta(hours=24)).timestamp() * 1000)

    # Create accounts.json with Unix timestamp
    accounts_data = {
        "version": 1,
        "accounts": {
            "unix-account": {
                "accessToken": "access_unix",
                "refreshToken": "refresh_unix",
                "expiresAt": unix_ts_ms,
            },
        },
    }
    json_path.write_text(json.dumps(accounts_data))

    # Run migration
    count = await migrate_from_accounts_json(json_path)
    assert count == 1

    # Verify account created with correct expiry
    repo = AccountRepository()
    account = await repo.get("unix-account")
    assert account is not None
    assert account.access_token == "access_unix"
    # Verify expiry is set (not default/now)
    assert account.token_expires_at is not None
    # The timestamp should be approximately 24 hours from now
    # Compare as naive datetimes since DB stores naive
    now_naive = datetime.now(UTC).replace(tzinfo=None)
    assert account.token_expires_at > now_naive
    assert account.token_expires_at < now_naive + timedelta(hours=25)
