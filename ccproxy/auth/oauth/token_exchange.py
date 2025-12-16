"""Shared OAuth token exchange utilities.

Centralizes OAuth 2.0 token exchange logic to avoid duplication across:
- ccproxy/ui/accounts.py (sync)
- ccproxy/auth/oauth/routes.py (async)
- ccproxy/services/credentials/oauth_client.py (async)
- ccproxy/rotation/refresh.py (async)

All token exchanges use JSON body format (application/json) as required
by Anthropic's OAuth API (not the standard OAuth 2.0 form-encoded format).
"""

from dataclasses import dataclass
from typing import Any

import httpx
from structlog import get_logger

from .constants import (
    OAUTH_AUTHORIZE_URL,
    OAUTH_BETA_VERSION,
    OAUTH_CLIENT_ID,
    OAUTH_REDIRECT_URI,
    OAUTH_SCOPES,
    OAUTH_TOKEN_URL,
    OAUTH_USER_AGENT,
)


logger = get_logger(__name__)


@dataclass
class OAuthConfig:
    """OAuth configuration with sensible defaults."""

    authorize_url: str = OAUTH_AUTHORIZE_URL
    token_url: str = OAUTH_TOKEN_URL
    client_id: str = OAUTH_CLIENT_ID
    redirect_uri: str = OAUTH_REDIRECT_URI
    scopes: list[str] | None = None  # Defaults to OAUTH_SCOPES if None
    beta_version: str = OAUTH_BETA_VERSION
    user_agent: str = OAUTH_USER_AGENT
    timeout: float = 30.0

    def __post_init__(self) -> None:
        """Set default scopes if not provided."""
        if self.scopes is None:
            self.scopes = OAUTH_SCOPES.copy()


class TokenExchangeError(Exception):
    """Raised when token exchange fails."""

    def __init__(self, message: str, status_code: int | None = None, response_text: str | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_text = response_text


def _build_headers(config: OAuthConfig) -> dict[str, str]:
    """Build standard OAuth headers for JSON requests."""
    return {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "anthropic-beta": config.beta_version,
        "User-Agent": config.user_agent,
    }


def _handle_error_response(response: httpx.Response, operation: str) -> None:
    """Handle error response and raise TokenExchangeError."""
    error_text = response.text[:500] if len(response.text) > 500 else response.text
    logger.error(
        f"oauth_{operation}_failed",
        status=response.status_code,
        error=error_text,
    )
    raise TokenExchangeError(
        f"{operation} failed: {error_text}",
        status_code=response.status_code,
        response_text=error_text,
    )


async def exchange_code_async(
    code: str,
    code_verifier: str,
    config: OAuthConfig | None = None,
) -> dict[str, Any]:
    """Exchange authorization code for tokens (async).

    Args:
        code: Authorization code from OAuth callback
        code_verifier: PKCE code verifier used in authorization request
        config: OAuth configuration (uses defaults if not provided)

    Returns:
        Token response dict with access_token, refresh_token, expires_in

    Raises:
        TokenExchangeError: If token exchange fails
    """
    if config is None:
        config = OAuthConfig()

    # Use JSON body format (not form-encoded) as required by Anthropic's OAuth endpoint
    token_data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": config.redirect_uri,
        "client_id": config.client_id,
        "code_verifier": code_verifier,
        "state": code_verifier,  # State matches code_verifier in PKCE flow
    }

    headers = _build_headers(config)

    async with httpx.AsyncClient() as client:
        response = await client.post(
            config.token_url,
            headers=headers,
            json=token_data,  # Use json= for JSON body instead of data= for form-encoded
            timeout=config.timeout,
        )

    if response.status_code != 200:
        _handle_error_response(response, "token_exchange")

    result: dict[str, Any] = response.json()
    return result


def exchange_code_sync(
    code: str,
    code_verifier: str,
    config: OAuthConfig | None = None,
) -> dict[str, Any]:
    """Exchange authorization code for tokens (sync).

    Args:
        code: Authorization code from OAuth callback
        code_verifier: PKCE code verifier used in authorization request
        config: OAuth configuration (uses defaults if not provided)

    Returns:
        Token response dict with access_token, refresh_token, expires_in

    Raises:
        TokenExchangeError: If token exchange fails
    """
    if config is None:
        config = OAuthConfig()

    # Use JSON body format (not form-encoded) as required by Anthropic's OAuth endpoint
    token_data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": config.redirect_uri,
        "client_id": config.client_id,
        "code_verifier": code_verifier,
        "state": code_verifier,  # State matches code_verifier in PKCE flow
    }

    headers = _build_headers(config)

    with httpx.Client() as client:
        response = client.post(
            config.token_url,
            headers=headers,
            json=token_data,  # Use json= for JSON body instead of data= for form-encoded
            timeout=config.timeout,
        )

    if response.status_code != 200:
        _handle_error_response(response, "token_exchange")

    result: dict[str, Any] = response.json()
    return result


async def refresh_token_async(
    refresh_token: str,
    config: OAuthConfig | None = None,
) -> dict[str, Any]:
    """Refresh access token (async).

    Args:
        refresh_token: Refresh token from previous token response
        config: OAuth configuration (uses defaults if not provided)

    Returns:
        Token response dict with new access_token, refresh_token, expires_in

    Raises:
        TokenExchangeError: If token refresh fails
    """
    if config is None:
        config = OAuthConfig()

    # Use JSON body format (not form-encoded) as required by Anthropic's OAuth endpoint
    token_data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": config.client_id,
    }

    headers = _build_headers(config)

    async with httpx.AsyncClient() as client:
        response = await client.post(
            config.token_url,
            headers=headers,
            json=token_data,  # Use json= for JSON body instead of data= for form-encoded
            timeout=config.timeout,
        )

    if response.status_code != 200:
        _handle_error_response(response, "token_refresh")

    result: dict[str, Any] = response.json()
    return result
