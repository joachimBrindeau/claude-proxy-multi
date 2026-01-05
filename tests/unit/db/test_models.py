"""Tests for database models."""

import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlmodel import select

from claude_code_proxy.db import Account, OAuthFlow, RateLimit, get_session, init_db


@pytest.fixture
async def db_session():
    """Create a temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        await init_db(db_path)
        async with get_session() as session:
            yield session


@pytest.mark.asyncio
async def test_account_create_and_retrieve(db_session):
    """Test creating and retrieving an account."""
    account = Account(
        name="test-account",
        access_token="access_123",
        refresh_token="refresh_456",
        token_expires_at=datetime.now(UTC) + timedelta(hours=24),
    )
    db_session.add(account)
    await db_session.commit()

    # Retrieve
    result = await db_session.execute(
        select(Account).where(Account.name == "test-account")
    )
    retrieved = result.scalar_one()

    assert retrieved.name == "test-account"
    assert retrieved.access_token == "access_123"
    assert retrieved.refresh_token == "refresh_456"
    assert retrieved.use_count == 0


@pytest.mark.asyncio
async def test_account_optional_fields(db_session):
    """Test account with optional profile fields."""
    account = Account(
        name="profile-account",
        access_token="access",
        refresh_token="refresh",
        token_expires_at=datetime.now(UTC) + timedelta(hours=24),
        email="user@example.com",
        display_name="Test User",
    )
    db_session.add(account)
    await db_session.commit()

    result = await db_session.execute(
        select(Account).where(Account.name == "profile-account")
    )
    retrieved = result.scalar_one()

    assert retrieved.email == "user@example.com"
    assert retrieved.display_name == "Test User"


@pytest.mark.asyncio
async def test_account_default_timestamps(db_session):
    """Test that account timestamps are set by default."""
    before = datetime.now(UTC)
    account = Account(
        name="timestamp-account",
        access_token="access",
        refresh_token="refresh",
        token_expires_at=datetime.now(UTC) + timedelta(hours=24),
    )
    db_session.add(account)
    await db_session.commit()
    after = datetime.now(UTC)

    result = await db_session.execute(
        select(Account).where(Account.name == "timestamp-account")
    )
    retrieved = result.scalar_one()

    # Verify timestamps were set
    assert retrieved.created_at is not None
    assert retrieved.updated_at is not None


@pytest.mark.asyncio
async def test_oauth_flow_create_and_retrieve(db_session):
    """Test OAuth flow creation and retrieval."""
    now = datetime.now(UTC)
    flow = OAuthFlow(
        state="code_verifier_123",
        account_name="test-account",
        created_at=now,
        expires_at=now + timedelta(hours=1),
        code_challenge="challenge_abc",
        redirect_uri="http://localhost:8080/callback",
    )
    db_session.add(flow)
    await db_session.commit()

    # Retrieve
    result = await db_session.execute(
        select(OAuthFlow).where(OAuthFlow.state == "code_verifier_123")
    )
    retrieved = result.scalar_one()

    assert retrieved.account_name == "test-account"
    assert retrieved.code_challenge == "challenge_abc"
    assert retrieved.redirect_uri == "http://localhost:8080/callback"


@pytest.mark.asyncio
async def test_oauth_flow_expiry(db_session):
    """Test OAuth flow with expiry."""
    now = datetime.now(UTC)
    flow = OAuthFlow(
        state="expiry_test_state",
        account_name="test-account",
        created_at=now,
        expires_at=now + timedelta(hours=1),
        code_challenge="challenge_abc",
        redirect_uri="http://localhost:8080/callback",
    )
    db_session.add(flow)
    await db_session.commit()

    # Retrieve
    result = await db_session.execute(
        select(OAuthFlow).where(OAuthFlow.state == "expiry_test_state")
    )
    retrieved = result.scalar_one()

    assert retrieved.expires_at > now


@pytest.mark.asyncio
async def test_oauth_flow_pkce_fields(db_session):
    """Test OAuth flow PKCE parameters are stored correctly."""
    now = datetime.now(UTC)
    code_challenge = "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"
    redirect_uri = "http://localhost:3000/api/auth/callback"

    flow = OAuthFlow(
        state="pkce_verifier_abc123",
        account_name="pkce-account",
        created_at=now,
        expires_at=now + timedelta(hours=1),
        code_challenge=code_challenge,
        redirect_uri=redirect_uri,
    )
    db_session.add(flow)
    await db_session.commit()

    result = await db_session.execute(
        select(OAuthFlow).where(OAuthFlow.state == "pkce_verifier_abc123")
    )
    retrieved = result.scalar_one()

    assert retrieved.code_challenge == code_challenge
    assert retrieved.redirect_uri == redirect_uri


@pytest.mark.asyncio
async def test_rate_limit_tracking(db_session):
    """Test rate limit persistence."""
    # First create an account (foreign key)
    account = Account(
        name="limited-account",
        access_token="access",
        refresh_token="refresh",
        token_expires_at=datetime.now(UTC) + timedelta(hours=24),
    )
    db_session.add(account)
    await db_session.commit()

    # Add rate limit
    now = datetime.now(UTC)
    rate_limit = RateLimit(
        account_name="limited-account",
        limited_at=now,
        resets_at=now + timedelta(minutes=30),
        triggered_by="/v1/messages",
    )
    db_session.add(rate_limit)
    await db_session.commit()

    # Retrieve
    result = await db_session.execute(
        select(RateLimit).where(RateLimit.account_name == "limited-account")
    )
    retrieved = result.scalar_one()

    assert retrieved.resets_at > now
    assert retrieved.triggered_by == "/v1/messages"


@pytest.mark.asyncio
async def test_rate_limit_without_triggered_by(db_session):
    """Test rate limit with optional triggered_by field."""
    # Create account first
    account = Account(
        name="minimal-rate-limit-account",
        access_token="access",
        refresh_token="refresh",
        token_expires_at=datetime.now(UTC) + timedelta(hours=24),
    )
    db_session.add(account)
    await db_session.commit()

    now = datetime.now(UTC)
    rate_limit = RateLimit(
        account_name="minimal-rate-limit-account",
        limited_at=now,
        resets_at=now + timedelta(minutes=15),
    )
    db_session.add(rate_limit)
    await db_session.commit()

    result = await db_session.execute(
        select(RateLimit).where(RateLimit.account_name == "minimal-rate-limit-account")
    )
    retrieved = result.scalar_one()

    assert retrieved.triggered_by is None
    assert retrieved.limited_at is not None


@pytest.mark.asyncio
async def test_multiple_accounts(db_session):
    """Test creating and retrieving multiple accounts."""
    accounts = [
        Account(
            name=f"account-{i}",
            access_token=f"access_{i}",
            refresh_token=f"refresh_{i}",
            token_expires_at=datetime.now(UTC) + timedelta(hours=24),
        )
        for i in range(3)
    ]
    for account in accounts:
        db_session.add(account)
    await db_session.commit()

    result = await db_session.execute(select(Account))
    retrieved = list(result.scalars().all())

    assert len(retrieved) == 3
    names = {a.name for a in retrieved}
    assert names == {"account-0", "account-1", "account-2"}


@pytest.mark.asyncio
async def test_account_update(db_session):
    """Test updating an account's tokens."""
    account = Account(
        name="update-account",
        access_token="old_access",
        refresh_token="old_refresh",
        token_expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    db_session.add(account)
    await db_session.commit()

    # Update tokens
    result = await db_session.execute(
        select(Account).where(Account.name == "update-account")
    )
    retrieved = result.scalar_one()
    retrieved.access_token = "new_access"
    retrieved.refresh_token = "new_refresh"
    retrieved.token_expires_at = datetime.now(UTC) + timedelta(hours=24)
    db_session.add(retrieved)
    await db_session.commit()

    # Verify update
    result = await db_session.execute(
        select(Account).where(Account.name == "update-account")
    )
    updated = result.scalar_one()

    assert updated.access_token == "new_access"
    assert updated.refresh_token == "new_refresh"
