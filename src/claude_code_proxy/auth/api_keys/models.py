"""Pydantic models for API key authentication."""

from datetime import UTC, datetime

from pydantic import BaseModel, Field


class APIKeyCreate(BaseModel):
    """Input model for creating a new API key."""

    user_id: str = Field(
        ..., min_length=1, max_length=100, description="User identifier"
    )
    description: str = Field(
        default="", max_length=255, description="Optional key description"
    )
    expires_days: int = Field(
        default=90, ge=1, le=365, description="Days until expiration"
    )


class APIKey(BaseModel):
    """API key metadata model."""

    key_id: str = Field(..., description="Unique key identifier")
    user_id: str = Field(..., description="User this key belongs to")
    description: str = Field(default="", description="Key description")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime = Field(..., description="Expiration timestamp")
    revoked: bool = Field(default=False, description="Whether key is revoked")
    revoked_at: datetime | None = Field(
        default=None, description="When key was revoked"
    )
