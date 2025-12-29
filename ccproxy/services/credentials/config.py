"""Configuration for credentials and OAuth."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field


if TYPE_CHECKING:
    from ccproxy.config.auth import OAuthSettings


def _get_default_storage_paths() -> list[str]:
    """Get default storage paths, with test override support."""
    # Allow tests to override credential paths
    if os.getenv("CCPROXY_TEST_MODE") == "true":
        # Use a test-specific location that won't pollute real credentials
        return [
            "/tmp/ccproxy-test/.config/claude/.credentials.json",
            "/tmp/ccproxy-test/.claude/.credentials.json",
        ]

    return [
        "~/.config/claude/.credentials.json",  # Alternative legacy location
        "~/.claude/.credentials.json",  # Legacy location
        "~/.config/ccproxy/credentials.json",  # location in app config
    ]


def _get_oauth_settings() -> OAuthSettings:
    """Lazy import OAuthSettings to avoid circular imports."""
    from ccproxy.config.auth import OAuthSettings

    return OAuthSettings()


class OAuthConfig(BaseModel):
    """OAuth configuration for credentials management.

    Note: For full OAuth settings, prefer importing OAuthSettings
    directly from ccproxy.config.auth.
    """

    authorize_url: str = Field(
        default="https://console.anthropic.com/oauth/authorize",
        description="OAuth authorization URL",
    )
    token_url: str = Field(
        default="https://console.anthropic.com/v1/oauth/token",
        description="OAuth token URL",
    )
    client_id: str = Field(
        default="9d1c250a-e61b-44d9-88ed-5944d1962f5e",
        description="OAuth client ID",
    )
    redirect_uri: str = Field(
        default="https://console.anthropic.com/oauth/native/callback",
        description="OAuth redirect URI",
    )
    scopes: list[str] = Field(
        default_factory=lambda: [
            "org:create_api_key",
            "user:profile",
            "user:inference",
        ],
        description="OAuth scopes to request",
    )


class CredentialsConfig(BaseModel):
    """Configuration for credentials management."""

    storage_paths: list[str] = Field(
        default_factory=lambda: _get_default_storage_paths(),
        description="Paths to search for credentials files",
    )
    oauth: OAuthConfig = Field(
        default_factory=OAuthConfig,
        description="OAuth configuration",
    )
    auto_refresh: bool = Field(
        default=True,
        description="Automatically refresh expired tokens",
    )
    refresh_buffer_seconds: int = Field(
        default=300,
        description="Refresh token this many seconds before expiry",
        ge=0,
    )
