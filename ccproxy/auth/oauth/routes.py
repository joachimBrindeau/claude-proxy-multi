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

from ccproxy.auth.exceptions import CredentialsStorageError
from ccproxy.auth.models import (
    ClaudeCredentials,
    OAuthToken,
)
from ccproxy.auth.oauth.token_exchange import (
    TokenExchangeConfig,
    TokenExchangeError,
    exchange_code_async,
)
from ccproxy.auth.storage import JsonFileTokenStorage as JsonFileStorage
from ccproxy.config.auth import OAuthSettings
from ccproxy.rotation.startup import InvalidAccountsPathError, get_accounts_path


logger = get_logger(__name__)

router = APIRouter(tags=["oauth"])

# Store for pending OAuth flows with 10-minute TTL to prevent memory leaks
# OAuth flows should complete within minutes; abandoned flows are auto-cleaned
_pending_flows: TTLCache[str, dict[str, Any]] = TTLCache(maxsize=1000, ttl=600)  # type: ignore[no-any-unimported]


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


def get_web_oauth_config() -> dict[str, Any]:
    """Get OAuth configuration with web redirect support."""
    base_config = OAuthSettings()

    # Allow override for web-based OAuth
    redirect_uri = os.getenv(
        "CCPROXY_OAUTH_REDIRECT_URI",
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


def register_oauth_flow(
    state: str,
    code_verifier: str,
    custom_paths: list[Path] | None = None,
    account_name: str | None = None,
    save_to_accounts: bool = False,
) -> None:
    """Register a pending OAuth flow.

    Args:
        state: State parameter for CSRF protection
        code_verifier: PKCE code verifier
        custom_paths: Custom paths for credential storage
        account_name: Name for the account (for rotation pool)
        save_to_accounts: If True, save to accounts.json instead of credentials.json
    """
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
        "Registered OAuth flow",
        state=state,
        account_name=account_name,
        save_to_accounts=save_to_accounts,
        operation="register_oauth_flow",
    )


def get_oauth_flow_result(state: str) -> dict[str, Any] | None:
    """Get and remove OAuth flow result."""
    return _pending_flows.pop(state, None)  # type: ignore[no-any-return]


@router.post("/start", response_model=OAuthStartResponse)
async def start_oauth_flow(body: OAuthStartRequest) -> OAuthStartResponse:
    """Start OAuth flow for adding a new account.

    Generates PKCE parameters and returns the authorization URL.
    The user should be redirected to this URL to authenticate.
    """
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
        "code": "true",  # Required: tells Claude to show code on callback page
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
        "OAuth flow started",
        account_name=body.account_name,
        state=state,
        redirect_uri=config["redirect_uri"],
    )

    return OAuthStartResponse(auth_url=auth_url, state=state)


@router.get("/start/{account_name}")
async def start_oauth_flow_redirect(account_name: str) -> RedirectResponse:
    """Start OAuth flow and redirect directly to authorization URL.

    This is a convenience endpoint that redirects the browser directly
    to the OAuth authorization page.
    """
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
    """Handle OAuth callback from Claude authentication.

    This endpoint receives the authorization code from Claude's OAuth flow
    and exchanges it for access tokens.
    """
    try:
        if error:
            error_msg = error_description or error or "OAuth authentication failed"
            logger.error(
                "OAuth callback error",
                error_type="oauth_error",
                error_message=error_msg,
                oauth_error=error,
                oauth_error_description=error_description,
                state=state,
                operation="oauth_callback",
            )

            # Update pending flow if state is provided
            if state and state in _pending_flows:
                _pending_flows[state].update(
                    {
                        "completed": True,
                        "success": False,
                        "error": error_msg,
                    }
                )

            return HTMLResponse(
                content=f"""
                <html>
                    <head><title>Login Failed</title></head>
                    <body>
                        <h1>Login Failed</h1>
                        <p>Error: {error_msg}</p>
                        <p>You can close this window and try again.</p>
                    </body>
                </html>
                """,
                status_code=400,
            )

        if not code:
            error_msg = "No authorization code received"
            logger.error(
                "OAuth callback missing authorization code",
                error_type="missing_code",
                error_message=error_msg,
                state=state,
                operation="oauth_callback",
            )

            if state and state in _pending_flows:
                _pending_flows[state].update(
                    {
                        "completed": True,
                        "success": False,
                        "error": error_msg,
                    }
                )

            return HTMLResponse(
                content=f"""
                <html>
                    <head><title>Login Failed</title></head>
                    <body>
                        <h1>Login Failed</h1>
                        <p>Error: {error_msg}</p>
                        <p>You can close this window and try again.</p>
                    </body>
                </html>
                """,
                status_code=400,
            )

        if not state:
            error_msg = "Missing state parameter"
            logger.error(
                "OAuth callback missing state parameter",
                error_type="missing_state",
                error_message=error_msg,
                operation="oauth_callback",
            )
            return HTMLResponse(
                content=f"""
                <html>
                    <head><title>Login Failed</title></head>
                    <body>
                        <h1>Login Failed</h1>
                        <p>Error: {error_msg}</p>
                        <p>You can close this window and try again.</p>
                    </body>
                </html>
                """,
                status_code=400,
            )

        # Check if this is a valid pending flow
        if state not in _pending_flows:
            error_msg = "Invalid or expired state parameter"
            logger.error(
                "OAuth callback with invalid state",
                error_type="invalid_state",
                error_message="Invalid or expired state parameter",
                state=state,
                operation="oauth_callback",
            )
            return HTMLResponse(
                content=f"""
                <html>
                    <head><title>Login Failed</title></head>
                    <body>
                        <h1>Login Failed</h1>
                        <p>Error: {error_msg}</p>
                        <p>You can close this window and try again.</p>
                    </body>
                </html>
                """,
                status_code=400,
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
            account_msg = f" as '{account_name}'" if account_name else ""
            logger.info(
                "OAuth login successful",
                state=state,
                account_name=account_name,
                operation="oauth_callback",
            )
            return HTMLResponse(
                content=f"""
                <!DOCTYPE html>
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
                        <script>
                            setTimeout(() => {{
                                window.location.href = '/accounts';
                            }}, 3000);
                        </script>
                    </body>
                </html>
                """,
                status_code=200,
            )
        else:
            error_msg = "Failed to exchange authorization code for tokens"
            logger.error(
                "OAuth token exchange failed",
                error_type="token_exchange_failed",
                error_message=error_msg,
                state=state,
                operation="oauth_callback",
            )
            return HTMLResponse(
                content=f"""
                <html>
                    <head><title>Login Failed</title></head>
                    <body>
                        <h1>Login Failed</h1>
                        <p>Error: {error_msg}</p>
                        <p>You can close this window and try again.</p>
                    </body>
                </html>
                """,
                status_code=500,
            )

    except (
        httpx.HTTPError,
        pydantic.ValidationError,
        CredentialsStorageError,
        ValueError,
        KeyError,
    ) as e:
        # HTTP errors from token exchange, validation errors, storage errors,
        # or missing data in OAuth flow
        logger.error(
            "Known error type in OAuth callback",
            error_type=type(e).__name__,
            error_message=str(e),
            state=state,
            operation="oauth_callback",
            exc_info=True,
        )

        if state and state in _pending_flows:
            _pending_flows[state].update(
                {
                    "completed": True,
                    "success": False,
                    "error": str(e),
                }
            )

        return HTMLResponse(
            content=f"""
            <html>
                <head><title>Login Error</title></head>
                <body>
                    <h1>Login Error</h1>
                    <p>An unexpected error occurred: {str(e)}</p>
                    <p>You can close this window and try again.</p>
                </body>
            </html>
            """,
            status_code=500,
        )
    except Exception as e:  # noqa: BLE001 - Catch-all for user-facing OAuth callback
        # Catch any unexpected exceptions to provide user-friendly error page
        logger.error(
            "Unexpected error in OAuth callback",
            error_type=type(e).__name__,
            error_message=str(e),
            state=state,
            operation="oauth_callback",
            exc_info=True,
        )

        if state and state in _pending_flows:
            _pending_flows[state].update(
                {
                    "completed": True,
                    "success": False,
                    "error": str(e),
                }
            )

        return HTMLResponse(
            content=f"""
            <html>
                <head><title>Login Error</title></head>
                <body>
                    <h1>Login Error</h1>
                    <p>An unexpected error occurred: {str(e)}</p>
                    <p>You can close this window and try again.</p>
                </body>
            </html>
            """,
            status_code=500,
        )


@router.post("/exchange")
async def exchange_oauth_code(body: OAuthExchangeRequest) -> JSONResponse:
    """Exchange an authorization code for tokens (manual code entry flow).

    This endpoint is used when the user manually copies the authorization code
    from Anthropic's callback page and pastes it into the UI.

    The flow is:
    1. Call POST /oauth/start to get auth_url and state
    2. User opens auth_url, signs in with Google
    3. Claude redirects to console.anthropic.com/oauth/code/callback
    4. That page displays the authorization code
    5. User copies code and calls this endpoint with {state, code}
    6. This endpoint exchanges the code for tokens and saves them
    """
    try:
        state = body.state.strip()
        code = body.code.strip()

        # Strip URL fragment if user accidentally copied it (e.g., code#u_userid)
        if "#" in code:
            code = code.split("#")[0]
            logger.debug(
                "stripped_url_fragment_from_code", operation="exchange_oauth_code"
            )

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

        # Check if this is a valid pending flow
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
            "Exchanging authorization code",
            account_name=account_name,
            state=state[:8] + "...",
            operation="exchange_oauth_code",
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
            logger.info(
                "OAuth code exchange successful",
                account_name=account_name,
                operation="exchange_oauth_code",
            )
            return JSONResponse(
                content={
                    "success": True,
                    "message": f"Account '{account_name}' added successfully!",
                    "account_name": account_name,
                },
                status_code=200,
            )
        else:
            logger.error(
                "OAuth code exchange failed",
                account_name=account_name,
                operation="exchange_oauth_code",
            )
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
        # HTTP errors from token exchange, validation errors, storage errors,
        # or missing data in OAuth flow
        logger.error(
            "Unexpected error in code exchange",
            error=str(e),
            operation="exchange_oauth_code",
            exc_info=True,
        )
        return JSONResponse(
            content={"success": False, "error": f"Unexpected error: {str(e)}"},
            status_code=500,
        )


async def _exchange_code_for_tokens(
    authorization_code: str,
    code_verifier: str,
    custom_paths: list[Path] | None = None,
    account_name: str | None = None,
    save_to_accounts: bool = False,
) -> bool:
    """Exchange authorization code for access tokens.

    Args:
        authorization_code: Code from OAuth callback
        code_verifier: PKCE code verifier
        custom_paths: Custom paths for credential storage
        account_name: Name for the account (when saving to accounts.json)
        save_to_accounts: If True, save to accounts.json for rotation pool
    """
    try:
        from datetime import UTC, datetime

        # Get OAuth config (supports web redirect override)
        config = get_web_oauth_config()

        # Build token exchange config
        exchange_config = TokenExchangeConfig(
            token_url=config["token_url"],
            client_id=config["client_id"],
            redirect_uri=config["redirect_uri"],
            beta_version=config["beta_version"],
            user_agent=config["user_agent"],
        )

        # Exchange code for tokens using shared module
        result = await exchange_code_async(
            code=authorization_code,
            code_verifier=code_verifier,
            config=exchange_config,
        )

        # Calculate expires_at from expires_in
        expires_in = result.get("expires_in")
        expires_at = None
        if expires_in:
            expires_at = int((datetime.now(UTC).timestamp() + expires_in) * 1000)

        # Create credentials object
        access_token = result.get("access_token")
        refresh_token = result.get("refresh_token")
        scopes = (
            result.get("scope", "").split() if result.get("scope") else config["scopes"]
        )
        subscription_type = result.get("subscription_type", "unknown")

        # Save to accounts.json if this is a web flow for rotation pool
        if save_to_accounts and account_name:
            from ccproxy.rotation.accounts import (
                Account,
                AccountCredentials,
                AccountsFile,
                load_accounts,
                save_accounts,
            )

            # Get accounts path from env (with validation)
            try:
                accounts_path = get_accounts_path(validate=True)
            except InvalidAccountsPathError as e:
                raise TokenExchangeError(f"Invalid accounts path: {e}") from e

            # Load existing accounts
            try:
                accounts_file = load_accounts(accounts_path)
            except FileNotFoundError:
                accounts_file = AccountsFile(version=1, accounts={})

            # Create new account - ensure we have valid tokens
            if not access_token or not refresh_token or expires_at is None:
                missing = []
                if not access_token:
                    missing.append("access_token")
                if not refresh_token:
                    missing.append("refresh_token")
                if expires_at is None:
                    missing.append("expires_at")
                raise TokenExchangeError(
                    f"Token response missing required fields: {', '.join(missing)}"
                )

            creds = AccountCredentials(
                access_token=access_token,
                refresh_token=refresh_token,
                expires_at=expires_at,
            )
            account = Account(name=account_name, credentials=creds)

            # Add to accounts
            accounts_file.accounts[account_name] = account

            # Save
            if not save_accounts(accounts_file, accounts_path):
                raise TokenExchangeError(
                    f"Failed to save account '{account_name}' to {accounts_path}"
                )

            logger.info(
                "OAuth credentials saved to accounts.json",
                account_name=account_name,
                subscription_type=subscription_type,
                operation="exchange_code_for_tokens",
            )
            return True

        # Otherwise save to credentials.json (legacy/CLI flow)
        oauth_data = {
            "accessToken": access_token,
            "refreshToken": refresh_token,
            "expiresAt": expires_at,
            "scopes": scopes,
            "subscriptionType": subscription_type,
        }

        credentials = ClaudeCredentials(claudeAiOauth=OAuthToken(**oauth_data))

        # Save credentials using CredentialsManager (lazy import to avoid circular import)
        from ccproxy.services.credentials.manager import CredentialsManager

        if custom_paths:
            # Use the first custom path for storage
            storage = JsonFileStorage(custom_paths[0])
            manager = CredentialsManager(storage=storage)
        else:
            manager = CredentialsManager()

        if not await manager.save(credentials):
            raise TokenExchangeError("Failed to save OAuth credentials to storage")

        logger.info(
            "Successfully saved OAuth credentials",
            subscription_type=subscription_type,
            scopes=scopes,
            operation="exchange_code_for_tokens",
        )
        return True

    except TokenExchangeError as e:
        logger.error(
            "Token exchange failed",
            error_type="token_exchange_failed",
            status_code=e.status_code,
            error_detail=e.response_text,
            operation="exchange_code_for_tokens",
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
        # HTTP errors, validation errors, credential storage failures,
        # file system errors, or missing/invalid data
        logger.error(
            "Error during token exchange",
            error_type="token_exchange_exception",
            error_message=str(e),
            operation="exchange_code_for_tokens",
            exc_info=True,
        )
        return False


# Inline oauth_proxy.py script content for download
# This avoids needing to package/mount the scripts directory
OAUTH_PROXY_SCRIPT = r'''#!/usr/bin/env python3
"""Local OAuth callback proxy for Claude account management.

This script runs a local HTTP server that catches OAuth callbacks from Claude
and forwards them to your remote ccproxy server.

Usage:
    python oauth_proxy.py [SERVER_URL]

    SERVER_URL: Your ccproxy server URL (default: https://claude.llm.klarc.eu)

Example:
    # Using default server
    python oauth_proxy.py

    # Custom server
    python oauth_proxy.py https://my-server.example.com

Then go to your server's /accounts page and click "Add Account".
"""

import http.server
import sys
import urllib.parse
import webbrowser
from typing import Any

# Configuration
DEFAULT_SERVER = "https://claude.llm.klarc.eu"
LISTEN_PORT = 54545
LISTEN_HOST = "localhost"


class OAuthProxyHandler(http.server.BaseHTTPRequestHandler):
    """Handler that redirects OAuth callbacks to the remote server."""

    server_url: str = DEFAULT_SERVER

    def do_GET(self) -> None:  # noqa: N802
        """Handle GET requests - redirect callbacks to server."""
        # Parse the request path
        parsed = urllib.parse.urlparse(self.path)

        # Handle favicon requests
        if parsed.path == "/favicon.ico":
            self.send_response(404)
            self.end_headers()
            return

        # Handle the OAuth callback
        if parsed.path == "/callback":
            # Get query parameters
            query = parsed.query

            # Build redirect URL to server
            redirect_url = f"{self.server_url}/oauth/callback?{query}"

            print(f"\n{'='*60}")
            print("OAuth callback received!")
            print(f"Redirecting to: {redirect_url}")
            print(f"{'='*60}\n")

            # Send redirect response
            self.send_response(302)
            self.send_header("Location", redirect_url)
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.end_headers()

            # Write a simple HTML page in case redirect doesn't work
            html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Redirecting...</title>
    <meta http-equiv="refresh" content="0;url={redirect_url}">
    <style>
        body {{ font-family: system-ui, sans-serif; max-width: 600px; margin: 50px auto; padding: 20px; text-align: center; }}
    </style>
</head>
<body>
    <h1>Redirecting...</h1>
    <p>If you're not redirected automatically, <a href="{redirect_url}">click here</a>.</p>
</body>
</html>"""
            self.wfile.write(html.encode())
            return

        # Handle root path - show status
        if parsed.path == "/" or parsed.path == "":
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()

            html = f"""<!DOCTYPE html>
<html>
<head>
    <title>OAuth Proxy Running</title>
    <style>
        body {{ font-family: system-ui, sans-serif; max-width: 600px; margin: 50px auto; padding: 20px; }}
        .status {{ color: #22c55e; font-size: 24px; }}
        code {{ background: #f1f5f9; padding: 2px 6px; border-radius: 4px; }}
        .config {{ background: #f8fafc; padding: 16px; border-radius: 8px; margin: 16px 0; }}
    </style>
</head>
<body>
    <h1><span class="status">●</span> OAuth Proxy Running</h1>

    <div class="config">
        <p><strong>Listening on:</strong> <code>http://{LISTEN_HOST}:{LISTEN_PORT}</code></p>
        <p><strong>Forwarding to:</strong> <code>{self.server_url}</code></p>
    </div>

    <h2>How to use:</h2>
    <ol>
        <li>Keep this terminal running</li>
        <li>Go to <a href="{self.server_url}/accounts" target="_blank">{self.server_url}/accounts</a></li>
        <li>Click "Add Account" and sign in with Google</li>
        <li>You'll be redirected back here, then to your server</li>
    </ol>

    <p><em>Waiting for OAuth callback...</em></p>
</body>
</html>"""
            self.wfile.write(html.encode())
            return

        # Unknown path
        self.send_response(404)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Not found")

    def log_message(self, format: str, *args: Any) -> None:
        """Custom log formatting."""
        print(f"[{self.log_date_time_string()}] {format % args}")


def main() -> None:
    """Run the OAuth proxy server."""
    # Get server URL from command line or use default
    server_url = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SERVER

    # Remove trailing slash
    server_url = server_url.rstrip("/")

    # Set the server URL on the handler class
    OAuthProxyHandler.server_url = server_url

    # Create and start server
    server = http.server.HTTPServer((LISTEN_HOST, LISTEN_PORT), OAuthProxyHandler)

    print(f"""
╔══════════════════════════════════════════════════════════════╗
║                    OAuth Callback Proxy                       ║
╠══════════════════════════════════════════════════════════════╣
║  Listening on: http://{LISTEN_HOST}:{LISTEN_PORT:<26}║
║  Forwarding to: {server_url:<43}║
╠══════════════════════════════════════════════════════════════╣
║  Instructions:                                                ║
║  1. Keep this terminal running                                ║
║  2. Go to {server_url}/accounts{' ':<31}║
║  3. Click "Add Account" and sign in with Google               ║
║  4. The callback will be forwarded to your server             ║
╚══════════════════════════════════════════════════════════════╝
""")

    # Open browser to show status page
    print("Opening status page in browser...")
    webbrowser.open(f"http://{LISTEN_HOST}:{LISTEN_PORT}")

    print("\nPress Ctrl+C to stop.\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n\nStopping proxy server...")
        server.shutdown()
        print("Goodbye!")


if __name__ == "__main__":
    main()
'''


@router.get("/proxy-script")
async def get_oauth_proxy_script() -> PlainTextResponse:
    """Download the OAuth callback proxy script.

    This Python script runs locally on your machine to forward OAuth callbacks
    from localhost to the remote server.
    """
    return PlainTextResponse(
        content=OAUTH_PROXY_SCRIPT,
        media_type="text/x-python",
        headers={
            "Content-Disposition": "attachment; filename=oauth_proxy.py",
        },
    )
