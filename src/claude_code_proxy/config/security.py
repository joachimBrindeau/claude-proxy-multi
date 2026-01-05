# src/claude_code_proxy/config/security.py
"""Security configuration settings."""

import secrets

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class SecuritySettings(BaseSettings):
    """Security-specific configuration settings."""

    model_config = SettingsConfigDict(
        env_prefix="CCPROXY_",
        case_sensitive=False,
        extra="ignore",
    )

    auth_token: str | None = Field(
        default=None,
        description="Bearer token for API authentication (optional)",
    )

    confirmation_timeout_seconds: int = Field(
        default=30,
        ge=5,
        le=300,
        description="Timeout in seconds for permission confirmation requests (5-300)",
    )

    # API Key settings
    api_keys_enabled: bool = Field(
        default=False,
        description="Enable per-user API key authentication",
    )

    api_key_secret: str | None = Field(
        default=None,
        description="Secret key for signing API key JWTs (auto-generated if not set)",
    )

    api_key_secret_generated: bool = Field(
        default=False,
        description="Whether the API key secret was auto-generated",
    )

    @model_validator(mode="after")
    def ensure_api_key_secret(self) -> "SecuritySettings":
        """Generate API key secret if not provided and API keys are enabled."""
        if self.api_keys_enabled and not self.api_key_secret:
            self.api_key_secret = secrets.token_hex(32)
            self.api_key_secret_generated = True
        return self
