"""Configuration for credentials and OAuth."""

import os

from pydantic import BaseModel, Field

from ccproxy.auth.oauth.constants import (
    OAUTH_AUTHORIZE_URL,
    OAUTH_BETA_VERSION,
    OAUTH_CLIENT_ID,
    OAUTH_REDIRECT_URI,
    OAUTH_SCOPES,
    OAUTH_TOKEN_URL,
    OAUTH_USER_AGENT,
)


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


class OAuthConfig(BaseModel):
    """OAuth configuration settings.

    Uses shared constants from ccproxy.auth.oauth.constants to ensure
    scope consistency across all OAuth implementations.
    """

    base_url: str = Field(
        default="https://console.anthropic.com",
        description="Base URL for OAuth API endpoints",
    )
    beta_version: str = Field(
        default=OAUTH_BETA_VERSION,
        description="OAuth beta version header",
    )
    token_url: str = Field(
        default=OAUTH_TOKEN_URL,
        description="OAuth token endpoint URL",
    )
    authorize_url: str = Field(
        default=OAUTH_AUTHORIZE_URL,
        description="OAuth authorization endpoint URL",
    )
    profile_url: str = Field(
        default="https://api.anthropic.com/api/oauth/profile",
        description="OAuth profile endpoint URL",
    )
    client_id: str = Field(
        default=OAUTH_CLIENT_ID,
        description="OAuth client ID",
    )
    redirect_uri: str = Field(
        default=OAUTH_REDIRECT_URI,
        description="OAuth redirect URI - uses Anthropic's code display page",
    )
    scopes: list[str] = Field(
        default_factory=lambda: OAUTH_SCOPES.copy(),
        description="OAuth scopes to request (from shared constants)",
    )
    request_timeout: int = Field(
        default=30,
        description="Timeout in seconds for OAuth requests",
    )
    user_agent: str = Field(
        default=OAUTH_USER_AGENT,
        description="User agent string for OAuth requests",
    )
    callback_timeout: int = Field(
        default=300,
        description="Timeout in seconds for OAuth callback",
        ge=60,
        le=600,
    )
    callback_port: int = Field(
        default=54545,
        description="Port for OAuth callback server",
        ge=1024,
        le=65535,
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
