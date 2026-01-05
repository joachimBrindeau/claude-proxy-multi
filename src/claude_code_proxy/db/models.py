"""SQLModel database models."""

from datetime import UTC, datetime

from sqlmodel import Field, SQLModel


class Account(SQLModel, table=True):
    """Account with OAuth credentials."""

    __tablename__ = "accounts"

    name: str = Field(primary_key=True, index=True)
    access_token: str
    refresh_token: str
    token_expires_at: datetime
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    # Optional profile info
    email: str | None = None
    display_name: str | None = None

    # Runtime state (persisted for restart survival)
    last_used_at: datetime | None = None
    use_count: int = Field(default=0)


class OAuthFlow(SQLModel, table=True):
    """Pending OAuth flow state."""

    __tablename__ = "oauth_flows"

    state: str = Field(primary_key=True)  # code_verifier
    account_name: str = Field(index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime  # created_at + 1 hour

    # PKCE parameters
    code_challenge: str
    redirect_uri: str


class RateLimit(SQLModel, table=True):
    """Rate limit tracking per account."""

    __tablename__ = "rate_limits"

    account_name: str = Field(primary_key=True, foreign_key="accounts.name")
    limited_at: datetime
    resets_at: datetime

    # Optional: track which endpoint triggered it
    triggered_by: str | None = None
