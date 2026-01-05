"""OAuth authentication routes for Anthropic OAuth login."""

import base64
import hashlib
import os
import secrets
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import httpx
import pydantic
from cachetools import TTLCache
from fastapi import APIRouter, Query, Request
from fastapi.responses import (
    HTMLResponse,
    JSONResponse,
    PlainTextResponse,
    RedirectResponse,
)
from pydantic import BaseModel, Field
from structlog import get_logger

from claude_code_proxy.auth.models import (
    ClaudeCredentials,
    OAuthToken,
)
from claude_code_proxy.auth.oauth.token_exchange import (
    TokenExchangeConfig,
    TokenExchangeError,
    exchange_code_async,
)
from claude_code_proxy.auth.storage import JsonFileTokenStorage as JsonFileStorage
from claude_code_proxy.config.auth import OAuthSettings
from claude_code_proxy.core.constants import (
    CACHE_MAXSIZE_MEDIUM,
    MILLISECONDS_PER_SECOND,
    OAUTH_FLOW_TTL,
)
from claude_code_proxy.exceptions import CredentialsStorageError
from claude_code_proxy.rotation.startup import (
    InvalidAccountsPathError,
    get_accounts_path,
)


logger = get_logger(__name__)

router = APIRouter(tags=["oauth"])

# Store for pending OAuth flows with 10-minute TTL to prevent memory leaks
# OAuth flows should complete within minutes; abandoned flows are auto-cleaned
_pending_flows: TTLCache[str, dict[str, Any]] = TTLCache(  # type: ignore[no-any-unimported]
    maxsize=CACHE_MAXSIZE_MEDIUM, ttl=OAUTH_FLOW_TTL
)

# Path to the OAuth proxy script
_OAUTH_PROXY_SCRIPT_PATH = Path(__file__).parent / "scripts" / "oauth_proxy.py"


# =============================================================================
# HTML Templates
# =============================================================================


def _error_html(title: str, message: str, status_code: int = 400) -> HTMLResponse:
    """Create standardized error HTML response."""
    return HTMLResponse(
        content=f"""<!DOCTYPE html>
<html>
<head>
    <title>{title}</title>
    <style>
        body {{ font-family: system-ui, sans-serif; max-width: 600px; margin: 50px auto; padding: 20px; text-align: center; }}
        h1 {{ color: #dc2626; }}
        .error {{ background: #fef2f2; padding: 16px; border-radius: 8px; margin: 16px 0; }}
    </style>
</head>
<body>
    <h1>{title}</h1>
    <div class="error"><p>{message}</p></div>
    <p>You can close this window and try again.</p>
</body>
</html>""",
        status_code=status_code,
    )


def _success_html(account_name: str | None = None) -> HTMLResponse:
    """Create success HTML response with redirect."""
    account_msg = f" as '{account_name}'" if account_name else ""
    return HTMLResponse(
        content=f"""<!DOCTYPE html>
<html>
<head>
    <title>Login Successful</title>
    <style>
        body {{ font-family: system-ui, sans-serif; max-width: 600px; margin: 50px auto; padding: 20px; text-align: center; }}
        .success {{ color: #22c55e; font-size: 48px; }}
        a {{ color: #3b82f6; text-decoration: none; }}
        a:hover {{ text-decoration: underline; }}
    </style>
</head>
<body>
    <div class="success">✅</div>
    <h1>Login Successful!</h1>
    <p>Account{account_msg} has been added to the rotation pool.</p>
    <p><a href="/accounts">← Back to Account Manager</a></p>
    <script>setTimeout(() => {{ window.location.href = '/accounts'; }}, 3000);</script>
</body>
</html>""",
        status_code=200,
    )


# =============================================================================
# Request/Response Models
# =============================================================================


class OAuthStartRequest(BaseModel):
    """Request body for starting OAuth flow."""

    account_name: str = Field(
        description="Name for the new account (lowercase alphanumeric with _ or -)"
    )


class OAuthStartResponse(BaseModel):
    """Response for OAuth start endpoint."""

    auth_url: str = Field(description="URL to redirect user to for authentication")
    state: str = Field(description="State parameter for this flow")


class OAuthExchangeRequest(BaseModel):
    """Request body for exchanging authorization code."""

    state: str = Field(description="State parameter from the OAuth start response")
    code: str = Field(description="Authorization code from Anthropic's callback page")


# =============================================================================
# Configuration
# =============================================================================


def get_web_oauth_config() -> dict[str, Any]:
    """Get OAuth configuration with web redirect support."""
    base_config = OAuthSettings()

    # Allow override for web-based OAuth
    redirect_uri = os.getenv(
        "CLAUDE_CODE_PROXY_OAUTH_REDIRECT_URI",
        base_config.redirect_uri,
    )

    return {
        "authorize_url": base_config.authorize_url,
        "token_url": base_config.token_url,
        "client_id": base_config.client_id,
        "redirect_uri": redirect_uri,
        "scopes": base_config.scopes,
        "beta_version": base_config.beta_version,
        "user_agent": base_config.user_agent,
    }


# =============================================================================
# OAuth Flow Management
# =============================================================================


def register_oauth_flow(
    state: str,
    code_verifier: str,
    custom_paths: list[Path] | None = None,
    account_name: str | None = None,
    save_to_accounts: bool = False,
) -> None:
    """Register a pending OAuth flow."""
    _pending_flows[state] = {
        "code_verifier": code_verifier,
        "custom_paths": custom_paths,
        "account_name": account_name,
        "save_to_accounts": save_to_accounts,
        "completed": False,
        "success": False,
        "error": None,
    }
    logger.debug(
        "oauth_flow_registered",
        state=state,
        account_name=account_name,
        save_to_accounts=save_to_accounts,
    )


def get_oauth_flow_result(state: str) -> dict[str, Any] | None:
    """Get and remove OAuth flow result."""
    return _pending_flows.pop(state, None)  # type: ignore[no-any-return]


def _update_flow_error(state: str | None, error: str) -> None:
    """Update pending flow with error status."""
    if state and state in _pending_flows:
        _pending_flows[state].update(
            {"completed": True, "success": False, "error": error}
        )


# =============================================================================
# Routes
# =============================================================================


@router.post("/start", response_model=OAuthStartResponse)
async def start_oauth_flow(body: OAuthStartRequest) -> OAuthStartResponse:
    """Start OAuth flow for adding a new account."""
    import re

    # Validate account name
    if not re.match(r"^[a-z0-9_-]+$", body.account_name):
        raise ValueError("Account name must be lowercase alphanumeric with _ or -")

    if len(body.account_name) > 32:
        raise ValueError("Account name too long (max 32 chars)")

    # Generate PKCE
    code_verifier = secrets.token_urlsafe(32)
    code_challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest())
        .decode()
        .rstrip("=")
    )

    # Generate state
    state = secrets.token_urlsafe(32)

    # Register flow
    register_oauth_flow(
        state=state,
        code_verifier=code_verifier,
        account_name=body.account_name,
        save_to_accounts=True,
    )

    # Build auth URL
    config = get_web_oauth_config()
    params = {
        "code": "true",
        "response_type": "code",
        "client_id": config["client_id"],
        "redirect_uri": config["redirect_uri"],
        "scope": " ".join(config["scopes"]),
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }

    auth_url = f"{config['authorize_url']}?{urlencode(params)}"

    logger.info(
        "oauth_flow_started",
        account_name=body.account_name,
        state=state,
        redirect_uri=config["redirect_uri"],
    )

    return OAuthStartResponse(auth_url=auth_url, state=state)


@router.get("/start/{account_name}")
async def start_oauth_flow_redirect(account_name: str) -> RedirectResponse:
    """Start OAuth flow and redirect directly to authorization URL."""
    response = await start_oauth_flow(OAuthStartRequest(account_name=account_name))
    return RedirectResponse(url=response.auth_url, status_code=302)


@router.get("/callback")
async def oauth_callback(
    request: Request,
    code: str | None = Query(None, description="Authorization code"),
    state: str | None = Query(None, description="State parameter"),
    error: str | None = Query(None, description="OAuth error"),
    error_description: str | None = Query(None, description="OAuth error description"),
) -> HTMLResponse:
    """Handle OAuth callback from Claude authentication."""
    try:
        # Handle OAuth error from provider
        if error:
            error_msg = error_description or error or "OAuth authentication failed"
            logger.exception(
                "oauth_callback_error",
                error=error,
                description=error_description,
                state=state,
            )
            _update_flow_error(state, error_msg)
            return _error_html("Login Failed", f"Error: {error_msg}")

        # Validate required parameters
        if not code:
            error_msg = "No authorization code received"
            logger.error("oauth_callback_missing_code", state=state)
            _update_flow_error(state, error_msg)
            return _error_html("Login Failed", f"Error: {error_msg}")

        if not state:
            logger.error("oauth_callback_missing_state")
            return _error_html("Login Failed", "Error: Missing state parameter")

        # Validate flow exists
        if state not in _pending_flows:
            logger.error("oauth_callback_invalid_state", state=state)
            return _error_html(
                "Login Failed", "Error: Invalid or expired state parameter"
            )

        # Get flow details
        flow = _pending_flows[state]
        code_verifier = flow["code_verifier"]
        custom_paths = flow.get("custom_paths")
        account_name = flow.get("account_name")
        save_to_accounts = flow.get("save_to_accounts", False)

        # Exchange authorization code for tokens
        success = await _exchange_code_for_tokens(
            code,
            code_verifier,
            custom_paths,
            account_name=account_name,
            save_to_accounts=save_to_accounts,
        )

        # Update flow result
        _pending_flows[state].update(
            {
                "completed": True,
                "success": success,
                "error": None if success else "Token exchange failed",
            }
        )

        if success:
            logger.info(
                "oauth_login_successful", state=state, account_name=account_name
            )
            return _success_html(account_name)
        error_msg = "Failed to exchange authorization code for tokens"
        logger.error("oauth_token_exchange_failed", state=state)
        return _error_html("Login Failed", f"Error: {error_msg}", status_code=500)

    except (
        httpx.HTTPError,
        pydantic.ValidationError,
        CredentialsStorageError,
        ValueError,
        KeyError,
    ) as e:
        logger.exception(
            "oauth_callback_known_error",
            error_type=type(e).__name__,
            error=str(e),
            state=state,
        )
        _update_flow_error(state, str(e))
        return _error_html("Login Error", f"An error occurred: {e}", status_code=500)

    except Exception as e:
        logger.exception(
            "oauth_callback_unexpected_error",
            error_type=type(e).__name__,
            error=str(e),
            state=state,
        )
        _update_flow_error(state, str(e))
        return _error_html(
            "Login Error", f"An unexpected error occurred: {e}", status_code=500
        )


@router.post("/exchange")
async def exchange_oauth_code(body: OAuthExchangeRequest) -> JSONResponse:
    """Exchange an authorization code for tokens (manual code entry flow)."""
    try:
        state = body.state.strip()
        code = body.code.strip()

        # Strip URL fragment if user accidentally copied it
        if "#" in code:
            code = code.split("#")[0]
            logger.debug("stripped_url_fragment_from_code")

        if not state:
            return JSONResponse(
                content={"success": False, "error": "Missing state parameter"},
                status_code=400,
            )

        if not code:
            return JSONResponse(
                content={"success": False, "error": "Missing authorization code"},
                status_code=400,
            )

        if state not in _pending_flows:
            return JSONResponse(
                content={
                    "success": False,
                    "error": "Invalid or expired state. Please start a new OAuth flow.",
                },
                status_code=400,
            )

        # Get flow details
        flow = _pending_flows[state]
        code_verifier = flow["code_verifier"]
        account_name = flow.get("account_name")
        save_to_accounts = flow.get("save_to_accounts", False)

        logger.info(
            "oauth_code_exchange_start",
            account_name=account_name,
            state=state[:8] + "...",
        )

        # Exchange authorization code for tokens
        success = await _exchange_code_for_tokens(
            code,
            code_verifier,
            account_name=account_name,
            save_to_accounts=save_to_accounts,
        )

        # Clean up the pending flow
        del _pending_flows[state]

        if success:
            logger.info("oauth_code_exchange_successful", account_name=account_name)
            return JSONResponse(
                content={
                    "success": True,
                    "message": f"Account '{account_name}' added successfully!",
                    "account_name": account_name,
                },
                status_code=200,
            )
        logger.error("oauth_code_exchange_failed", account_name=account_name)
        return JSONResponse(
            content={
                "success": False,
                "error": "Failed to exchange code for tokens. The code may be invalid or expired.",
            },
            status_code=400,
        )

    except (
        httpx.HTTPError,
        pydantic.ValidationError,
        CredentialsStorageError,
        ValueError,
        KeyError,
    ) as e:
        logger.exception("oauth_exchange_error", error=str(e))
        return JSONResponse(
            content={"success": False, "error": f"Unexpected error: {e}"},
            status_code=500,
        )


@router.get("/proxy-script")
async def get_oauth_proxy_script() -> PlainTextResponse:
    """Download the OAuth callback proxy script."""
    try:
        content = _OAUTH_PROXY_SCRIPT_PATH.read_text()
    except FileNotFoundError:
        logger.exception(
            "oauth_proxy_script_not_found", path=str(_OAUTH_PROXY_SCRIPT_PATH)
        )
        return PlainTextResponse(content="# Script not found", status_code=404)

    return PlainTextResponse(
        content=content,
        media_type="text/x-python",
        headers={"Content-Disposition": "attachment; filename=oauth_proxy.py"},
    )


# =============================================================================
# Token Exchange
# =============================================================================


async def _exchange_code_for_tokens(
    authorization_code: str,
    code_verifier: str,
    custom_paths: list[Path] | None = None,
    account_name: str | None = None,
    save_to_accounts: bool = False,
) -> bool:
    """Exchange authorization code for access tokens."""
    try:
        from datetime import UTC, datetime

        # Get OAuth config
        config = get_web_oauth_config()

        # Build token exchange config
        exchange_config = TokenExchangeConfig(
            token_url=config["token_url"],
            client_id=config["client_id"],
            redirect_uri=config["redirect_uri"],
            beta_version=config["beta_version"],
            user_agent=config["user_agent"],
        )

        # Exchange code for tokens
        result = await exchange_code_async(
            code=authorization_code, code_verifier=code_verifier, config=exchange_config
        )

        # Calculate expires_at
        expires_in = result.get("expires_in")
        expires_at = None
        if expires_in:
            expires_at = int(
                (datetime.now(UTC).timestamp() + expires_in) * MILLISECONDS_PER_SECOND
            )

        # Extract token data
        access_token = result.get("access_token")
        refresh_token = result.get("refresh_token")
        scopes = (
            result.get("scope", "").split() if result.get("scope") else config["scopes"]
        )
        subscription_type = result.get("subscription_type", "unknown")

        # Save to accounts.json for rotation pool
        if save_to_accounts and account_name:
            return await _save_to_accounts_file(
                account_name, access_token, refresh_token, expires_at
            )

        # Otherwise save to credentials.json (legacy/CLI flow)
        return await _save_to_credentials_file(
            access_token,
            refresh_token,
            expires_at,
            scopes,
            subscription_type,
            custom_paths,
        )

    except TokenExchangeError as e:
        logger.exception(
            "token_exchange_failed",
            status_code=e.status_code,
            error_detail=e.response_text,
        )
        return False

    except (
        httpx.HTTPError,
        pydantic.ValidationError,
        CredentialsStorageError,
        OSError,
        ValueError,
        KeyError,
    ) as e:
        logger.exception(
            "token_exchange_exception",
            error_type=type(e).__name__,
            error=str(e),
        )
        return False


async def _save_to_accounts_file(
    account_name: str,
    access_token: str | None,
    refresh_token: str | None,
    expires_at: int | None,
) -> bool:
    """Save credentials to accounts.json for rotation pool."""
    from claude_code_proxy.rotation.accounts import (
        Account,
        AccountCredentials,
        AccountsFile,
        load_accounts,
        save_accounts,
    )

    # Validate required fields
    if not access_token or not refresh_token or expires_at is None:
        missing = [
            f
            for f, v in [
                ("access_token", access_token),
                ("refresh_token", refresh_token),
                ("expires_at", expires_at),
            ]
            if not v
        ]
        raise TokenExchangeError(
            f"Token response missing required fields: {', '.join(missing)}"
        )

    # Get accounts path
    try:
        accounts_path = get_accounts_path(validate=True)
    except InvalidAccountsPathError as e:
        raise TokenExchangeError(f"Invalid accounts path: {e}") from e

    # Load existing accounts
    try:
        accounts_file = load_accounts(accounts_path)
    except FileNotFoundError:
        accounts_file = AccountsFile(version=1, accounts={})

    # Create new account
    creds = AccountCredentials(
        access_token=access_token, refresh_token=refresh_token, expires_at=expires_at
    )
    account = Account(name=account_name, credentials=creds)

    # Add and save
    accounts_file.accounts[account_name] = account
    if not save_accounts(accounts_file, accounts_path):
        raise TokenExchangeError(
            f"Failed to save account '{account_name}' to {accounts_path}"
        )

    logger.info("oauth_credentials_saved_to_accounts", account_name=account_name)
    return True


async def _save_to_credentials_file(
    access_token: str | None,
    refresh_token: str | None,
    expires_at: int | None,
    scopes: list[str],
    subscription_type: str,
    custom_paths: list[Path] | None = None,
) -> bool:
    """Save credentials to credentials.json (legacy/CLI flow)."""
    from claude_code_proxy.services.credentials.manager import CredentialsManager

    if not access_token or not refresh_token:
        raise TokenExchangeError(
            "Cannot save credentials without access and refresh tokens"
        )

    credentials = ClaudeCredentials(
        claudeAiOauth=OAuthToken(
            accessToken=access_token,
            refreshToken=refresh_token,
            expiresAt=expires_at,
            scopes=scopes,
            subscriptionType=subscription_type,
        )
    )

    if custom_paths:
        storage = JsonFileStorage(custom_paths[0])
        manager = CredentialsManager(storage=storage)
    else:
        manager = CredentialsManager()

    if not await manager.save(credentials):
        raise TokenExchangeError("Failed to save OAuth credentials to storage")

    logger.info(
        "oauth_credentials_saved", subscription_type=subscription_type, scopes=scopes
    )
    return True
