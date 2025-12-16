"""HTMX UI for Claude account management.

Provides a web interface to:
- View account status and rotation pool
- Add new accounts via OAuth
- Enable/disable accounts
"""

import base64
import hashlib
import os
import re
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlencode

from fastapi import APIRouter, FastAPI, Form, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates
from structlog import get_logger

from ccproxy.auth.oauth.constants import (
    OAUTH_AUTHORIZE_URL,
    OAUTH_CLIENT_ID,
    OAUTH_REDIRECT_URI,
    OAUTH_SCOPES,
)
from ccproxy.auth.oauth.token_exchange import OAuthConfig, exchange_code_async
from ccproxy.rotation.accounts import (
    Account,
    AccountCredentials,
    AccountsFile,
    load_accounts,
    save_accounts,
)
from ccproxy.rotation.capacity_check import CapacityInfo, check_capacity_async
from ccproxy.rotation.pool import RotationPool


logger = get_logger(__name__)

# Templates directory
TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# OAuth flow TTL in seconds (1 hour)
OAUTH_FLOW_TTL_SECONDS = 3600


@dataclass
class OAuthFlowState:
    """State for a pending OAuth flow with expiration."""

    account_name: str
    created_at: datetime

    def is_expired(self, ttl_seconds: int = OAUTH_FLOW_TTL_SECONDS) -> bool:
        """Check if flow has expired."""
        age = (datetime.now(UTC) - self.created_at).total_seconds()
        return age > ttl_seconds


# In-memory storage: Maps code_verifier (state) to OAuth flow state
_pending_oauth_flows: dict[str, OAuthFlowState] = {}


def _cleanup_expired_flows() -> int:
    """Remove expired OAuth flows. Returns count removed."""
    expired = [
        state
        for state, flow in _pending_oauth_flows.items()
        if flow.is_expired()
    ]
    for state in expired:
        logger.info("oauth_flow_expired_cleanup", state=state[:8] + "...")
        _pending_oauth_flows.pop(state, None)
    return len(expired)


def _get_pending_account_names() -> list[str]:
    """Get list of account names with pending (non-expired) flows."""
    return [
        flow.account_name
        for flow in _pending_oauth_flows.values()
        if not flow.is_expired()
    ]


@dataclass
class AccountView:
    """Account data for template rendering."""
    name: str
    state: str
    expires_in: str
    is_expired: bool
    rate_limited_until: str | None = None
    last_used: str | None = None
    last_error: str | None = None
    is_next: bool = False
    # Capacity info
    tokens_remaining_percent: float | None = None
    requests_remaining_percent: float | None = None
    capacity_checked_at: str | None = None


def get_accounts_path() -> Path:
    """Get accounts.json path from environment or default."""
    path_str = os.getenv("CCPROXY_ACCOUNTS_PATH", "~/.claude/accounts.json")
    return Path(path_str).expanduser()


def format_expires_in(seconds: int | None) -> str:
    """Format seconds until expiration as human-readable string."""
    if seconds is None:
        return "-"
    if seconds < 0:
        return "Expired"
    hours, remainder = divmod(seconds, 3600)
    minutes = remainder // 60
    if hours > 24:
        return f"{hours // 24}d {hours % 24}h"
    return f"{hours}h {minutes}m"


def format_rate_limit_reset(iso_str: str | None) -> str | None:
    """Format rate limit reset time as human-readable countdown."""
    if not iso_str:
        return None
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        now = datetime.now(UTC)
        if dt <= now:
            return None  # Already reset
        delta = dt - now
        total_seconds = int(delta.total_seconds())
        if total_seconds < 60:
            return f"{total_seconds}s"
        minutes = total_seconds // 60
        if minutes < 60:
            return f"{minutes}m"
        hours = minutes // 60
        remaining_minutes = minutes % 60
        return f"{hours}h {remaining_minutes}m"
    except Exception:
        return None


def format_last_used(iso_str: str | None) -> str | None:
    """Format last used time as human-readable relative time."""
    if not iso_str:
        return None
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        now = datetime.now(UTC)
        delta = now - dt
        total_seconds = int(delta.total_seconds())
        if total_seconds < 0:
            return None
        if total_seconds < 60:
            return "Just now"
        minutes = total_seconds // 60
        if minutes < 60:
            return f"{minutes}m ago"
        hours = minutes // 60
        if hours < 24:
            return f"{hours}h ago"
        days = hours // 24
        return f"{days}d ago"
    except Exception:
        return None


def format_capacity_checked(iso_str: str | None) -> str | None:
    """Format capacity check time as human-readable relative time."""
    return format_last_used(iso_str)  # Same format


def get_capacity_color(percent: float | None) -> str:
    """Get Tailwind color class for capacity percentage."""
    if percent is None:
        return "text-slate-400"
    if percent > 75:
        return "text-emerald-600"
    if percent > 25:
        return "text-amber-600"
    return "text-red-600"


def get_pool(request: Request) -> RotationPool | None:
    """Get rotation pool from app state."""
    return getattr(request.app.state, "rotation_pool", None)


def is_token_expired(expires_at_str: str) -> bool:
    """Check if a token is expired based on expiration timestamp string."""
    if not expires_at_str:
        return False
    try:
        dt = datetime.fromisoformat(expires_at_str.replace("Z", "+00:00"))
        return datetime.now(UTC) > dt
    except Exception:
        return False


def get_accounts(request: Request) -> list[AccountView]:
    """Get account data for template rendering."""
    pool = get_pool(request)
    if pool is None:
        return []

    status = pool.get_status()
    next_account = status.get("nextAccount")
    accounts = []

    for info in status.get("accounts", []):
        expires_at_str = info.get("tokenExpiresAt", "")
        expired = is_token_expired(expires_at_str)
        name = info.get("name", "Unknown")

        accounts.append(AccountView(
            name=name,
            state=info.get("state", "unknown"),
            expires_in=format_expires_in(info.get("tokenExpiresIn")),
            is_expired=expired,
            rate_limited_until=format_rate_limit_reset(info.get("rateLimitedUntil")),
            last_used=format_last_used(info.get("lastUsed")),
            last_error=info.get("lastError"),
            is_next=(name == next_account),
            # Capacity info
            tokens_remaining_percent=info.get("tokensRemainingPercent"),
            requests_remaining_percent=info.get("requestsRemainingPercent"),
            capacity_checked_at=format_capacity_checked(info.get("capacityCheckedAt")),
        ))

    return accounts


def get_summary(request: Request) -> str:
    """Get summary HTML for account pool."""
    pool = get_pool(request)
    if pool is None:
        return "Pool not initialized"

    status = pool.get_status()
    total = status.get("totalAccounts", 0)
    rate_limited = status.get("rateLimitedAccounts", 0)
    auth_error = status.get("authErrorAccounts", 0)

    if total == 0:
        return "No accounts configured"

    # Count expired tokens
    accounts = status.get("accounts", [])
    expired_count = sum(
        1 for acc in accounts
        if acc.get("state") == "available" and is_token_expired(acc.get("tokenExpiresAt", ""))
    )

    available = status.get("availableAccounts", 0)
    effective_errors = auth_error + expired_count

    parts = [f"<strong>{available}/{total}</strong> ready"]
    if rate_limited:
        parts.append(f"<strong>{rate_limited}</strong> limited")
    if effective_errors:
        parts.append(f"<strong>{effective_errors}</strong> expired")

    return " &middot; ".join(parts)


def generate_pkce() -> tuple[str, str]:
    """Generate PKCE code verifier and challenge."""
    code_verifier = secrets.token_urlsafe(32)
    digest = hashlib.sha256(code_verifier.encode()).digest()
    code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return code_verifier, code_challenge


def validate_account_name(name: str) -> str | None:
    """Validate account name. Returns error message or None if valid."""
    if not name:
        return "Account name is required"
    if not re.match(r"^[a-z0-9_-]+$", name):
        return "Invalid name: use lowercase, numbers, hyphens only"
    if len(name) > 32:
        return "Account name too long (max 32 chars)"
    return None


def generate_auth_url(account_name: str) -> tuple[str, str]:
    """Generate OAuth authorization URL and store PKCE verifier."""
    # Cleanup expired flows before creating new one
    _cleanup_expired_flows()

    code_verifier, code_challenge = generate_pkce()
    _pending_oauth_flows[code_verifier] = OAuthFlowState(
        account_name=account_name,
        created_at=datetime.now(UTC),
    )

    params = {
        "code": "true",
        "client_id": OAUTH_CLIENT_ID,
        "response_type": "code",
        "redirect_uri": OAUTH_REDIRECT_URI,
        "scope": " ".join(OAUTH_SCOPES),
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "state": code_verifier,
    }

    auth_url = f"{OAUTH_AUTHORIZE_URL}?{urlencode(params)}"
    logger.info("oauth_flow_started", account=account_name)
    return auth_url, code_verifier


# Router
router = APIRouter(prefix="/accounts", tags=["accounts"])


def render_page(
    request: Request,
    status_message: str = "",
    show_oauth: bool = False,
    oauth_url: str = "",
    oauth_state: str = "",
    oauth_account: str = "",
) -> HTMLResponse:
    """Render the accounts page."""
    return templates.TemplateResponse("accounts.html", {
        "request": request,
        "accounts": get_accounts(request),
        "summary": get_summary(request),
        "status_message": status_message,
        "show_oauth": show_oauth,
        "oauth_url": oauth_url,
        "oauth_state": oauth_state,
        "oauth_account": oauth_account,
    })


@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def accounts_page(request: Request) -> HTMLResponse:
    """Main accounts page."""
    return render_page(request)


@router.get("/refresh", response_class=HTMLResponse)
async def refresh_accounts(request: Request) -> HTMLResponse:
    """Refresh accounts table (HTMX partial)."""
    return templates.TemplateResponse("partials/accounts_table.html", {
        "request": request,
        "accounts": get_accounts(request),
    })


@router.get("/start/{account_name}")
async def start_oauth_redirect(request: Request, account_name: str) -> Response:
    """Start OAuth flow and show authentication steps.

    This endpoint:
    1. Validates the account name
    2. Generates PKCE parameters and stores flow state
    3. Shows the OAuth link and code paste form
    """
    name = account_name.strip().lower()

    if error := validate_account_name(name):
        return render_page(request, status_message=error)

    auth_url, state = generate_auth_url(name)
    logger.info("oauth_flow_started", account=name, state=state[:8] + "...")

    return render_page(
        request,
        show_oauth=True,
        oauth_url=auth_url,
        oauth_state=state,
        oauth_account=name,
    )


def build_auth_url_for_state(state: str) -> str:
    """Build OAuth URL using existing state (code_verifier) without creating new mapping.

    Args:
        state: State parameter (code_verifier) from OAuth flow

    Returns:
        OAuth authorization URL

    Raises:
        ValueError: If state format is invalid
    """
    # Validate state format (base64url: alphanumeric + - and _)
    if not state or not re.match(r"^[A-Za-z0-9_-]{32,}$", state):
        raise ValueError(
            f"Invalid state format: expected base64url string of 32+ chars, "
            f"got '{state[:10]}...'" if len(state) > 10 else f"got '{state}'"
        )

    # Compute code_challenge from state (which is the code_verifier)
    digest = hashlib.sha256(state.encode()).digest()
    code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()

    params = {
        "code": "true",
        "client_id": OAUTH_CLIENT_ID,
        "response_type": "code",
        "redirect_uri": OAUTH_REDIRECT_URI,
        "scope": " ".join(OAUTH_SCOPES),
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "state": state,
    }

    return f"{OAUTH_AUTHORIZE_URL}?{urlencode(params)}"


@router.get("/return", response_class=HTMLResponse)
async def oauth_return(request: Request, state: str = "") -> HTMLResponse:
    """Return page after OAuth - shows code paste form.

    User lands here after completing OAuth at Claude.
    They need to paste the authorization code from the callback page.
    """
    if not state:
        return render_page(request, status_message="Missing state parameter")

    flow = _pending_oauth_flows.get(state)
    if not flow or flow.is_expired():
        if flow:
            # Clean up expired flow
            _pending_oauth_flows.pop(state, None)
        return render_page(request, status_message="Invalid or expired OAuth flow. Please start again.")

    # Rebuild auth URL using existing state (don't create new state mapping)
    auth_url = build_auth_url_for_state(state)

    return render_page(
        request,
        show_oauth=True,
        oauth_url=auth_url,
        oauth_state=state,
        oauth_account=flow.account_name,
    )


@router.delete("/delete/{name}", response_class=HTMLResponse)
async def delete_account(request: Request, name: str) -> HTMLResponse:
    """Delete an account."""
    try:
        path = get_accounts_path()
        accounts_file = load_accounts(path)

        if name not in accounts_file.accounts:
            return render_page(request, status_message=f"Account {name} not found")

        del accounts_file.accounts[name]

        if not save_accounts(accounts_file, path):
            return render_page(request, status_message="Failed to save changes")

        logger.info("account_removed_via_ui", account=name)

        pool = get_pool(request)
        if pool:
            pool.load()

        return render_page(request, status_message=f"Account {name} removed")

    except Exception as e:
        return render_page(request, status_message=f"Error: {e}")


@router.post("/rename/{old_name}", response_class=HTMLResponse)
async def rename_account(
    request: Request,
    old_name: str,
    new_name: str = Form(...),
) -> HTMLResponse:
    """Rename an account."""
    new_name = new_name.strip().lower()

    if error := validate_account_name(new_name):
        return render_page(request, status_message=error)

    if new_name == old_name:
        return render_page(request, status_message="New name is same as old name")

    try:
        path = get_accounts_path()
        accounts_file = load_accounts(path)

        if old_name not in accounts_file.accounts:
            return render_page(request, status_message=f"Account {old_name} not found")

        if new_name in accounts_file.accounts:
            return render_page(request, status_message=f"Account {new_name} already exists")

        # Move account to new name
        account = accounts_file.accounts[old_name]
        account.name = new_name
        accounts_file.accounts[new_name] = account
        del accounts_file.accounts[old_name]

        if not save_accounts(accounts_file, path):
            return render_page(request, status_message="Failed to save changes")

        logger.info("account_renamed_via_ui", old_name=old_name, new_name=new_name)

        pool = get_pool(request)
        if pool:
            pool.load()

        return render_page(request, status_message=f"Account renamed: {old_name} → {new_name}")

    except Exception as e:
        return render_page(request, status_message=f"Error: {e}")


def _validate_oauth_flow_state(
    state: str,
) -> tuple[OAuthFlowState | None, str | None]:
    """Validate OAuth flow state and return flow or error message.

    Args:
        state: The OAuth state parameter

    Returns:
        Tuple of (flow, error_message). One will be None.
    """
    flow = _pending_oauth_flows.get(state)
    if not flow or flow.is_expired():
        age_seconds = None
        if flow:
            # Calculate age before cleanup
            age_seconds = (datetime.now(UTC) - flow.created_at).total_seconds()
            # Clean up expired flow
            _pending_oauth_flows.pop(state, None)

        pending_accounts = _get_pending_account_names()
        logger.warning(
            "oauth_state_not_found",
            state_prefix=state[:8] + "..." if len(state) > 8 else state,
            pending_accounts=pending_accounts,
            active_flows=len(_pending_oauth_flows),
            expired=flow is not None,
            age_seconds=age_seconds,
        )
        return None, "Invalid or expired state. Start a new OAuth flow."
    return flow, None


def _validate_token_response(
    token_response: dict[str, object],
) -> tuple[str, str, int] | None:
    """Validate token response and extract required fields.

    Args:
        token_response: Response from token exchange

    Returns:
        Tuple of (access_token, refresh_token, expires_in) or None if invalid.
    """
    access_token = token_response.get("access_token")
    refresh_token = token_response.get("refresh_token")
    expires_in = token_response.get("expires_in", 86400)

    if not access_token or not refresh_token:
        return None

    if not isinstance(access_token, str) or not isinstance(refresh_token, str):
        return None

    if not isinstance(expires_in, int):
        expires_in = 86400

    return access_token, refresh_token, expires_in


def _save_account_credentials(
    account_name: str,
    access_token: str,
    refresh_token: str,
    expires_at: int,
) -> tuple[bool, bool]:
    """Save account credentials to the accounts file.

    Handles loading existing accounts or creating a new file if needed.

    Args:
        account_name: Name of the account
        access_token: OAuth access token
        refresh_token: OAuth refresh token
        expires_at: Token expiration timestamp in milliseconds

    Returns:
        Tuple of (success, is_new_account)
    """
    path = get_accounts_path()
    try:
        accounts_file = load_accounts(path)
    except FileNotFoundError:
        accounts_file = AccountsFile(version=1, accounts={})

    is_new = account_name not in accounts_file.accounts
    accounts_file.accounts[account_name] = Account(
        name=account_name,
        credentials=AccountCredentials(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=expires_at,
        ),
    )

    success = save_accounts(accounts_file, path)
    return success, is_new


async def _check_and_update_account_capacity(
    account_name: str,
    pool: RotationPool | None,
) -> str:
    """Check account capacity and update pool if available.

    Args:
        account_name: Name of the account to check
        pool: Optional rotation pool to update

    Returns:
        Status message string (empty if no message)
    """
    try:
        capacity = await check_capacity_async(account_name)
        if pool:
            account = pool.get_account(account_name)
            if account:
                account.update_capacity(
                    tokens_limit=capacity.tokens_limit,
                    tokens_remaining=capacity.tokens_remaining,
                    requests_limit=capacity.requests_limit,
                    requests_remaining=capacity.requests_remaining,
                )
        if capacity.error:
            return f" (Capacity check: {capacity.error})"
        elif capacity.tokens_remaining_percent is not None:
            return f" ({capacity.tokens_remaining_percent:.0f}% tokens remaining)"
    except Exception as e:
        logger.warning("capacity_check_after_oauth_failed", error=str(e))
    return ""


@router.post("/complete-oauth", response_class=HTMLResponse)
async def complete_oauth(
    request: Request,
    code: str = Form(...),
    state: str = Form(...),
) -> HTMLResponse:
    """Complete OAuth flow and save account."""
    if not code or not state:
        return render_page(request, status_message="Both code and state are required")

    # Sanitize inputs
    code = code.strip()
    state = state.strip()

    # Validate input lengths to prevent abuse
    if len(code) > 1000 or len(state) > 100:
        logger.warning("oauth_suspicious_input", code_len=len(code), state_len=len(state))
        return render_page(request, status_message="Invalid input parameters")

    # Strip URL fragments (user may accidentally copy them)
    code = code.split("#")[0]
    state = state.split("#")[0]

    # Validate OAuth flow state
    flow, error_msg = _validate_oauth_flow_state(state)
    if error_msg:
        return render_page(request, status_message=error_msg)
    assert flow is not None  # Type narrowing

    account_name = flow.account_name
    logger.info(
        "oauth_completing",
        account=account_name,
        state_prefix=state[:8] + "...",
    )

    try:
        token_response = await exchange_code_async(code, state, OAuthConfig())
        token_data = _validate_token_response(token_response)
        if not token_data:
            return render_page(request, status_message="Token response missing required fields")

        access_token, refresh_token, expires_in = token_data
        expires_at = int((datetime.now(UTC).timestamp() + expires_in) * 1000)

        success, is_new = _save_account_credentials(
            account_name, access_token, refresh_token, expires_at
        )
        if not success:
            return render_page(request, status_message="Failed to save account")

        action = "added" if is_new else "updated"
        logger.info(f"account_{action}_via_oauth", account=account_name)
        _pending_oauth_flows.pop(state, None)

        pool = get_pool(request)
        if pool:
            pool.load()

        capacity_msg = await _check_and_update_account_capacity(account_name, pool)
        return render_page(request, status_message=f"Account {account_name} {action} successfully!{capacity_msg}")

    except Exception as e:
        logger.error("oauth_exchange_failed", error=str(e))
        return render_page(request, status_message=f"Token exchange failed: {e}")


@router.post("/cancel-oauth", response_class=HTMLResponse)
async def cancel_oauth(
    request: Request,
    state: str = Form(default=""),
) -> HTMLResponse:
    """Cancel OAuth flow and clean up pending state."""
    if not state:
        logger.warning("oauth_cancel_without_state")
        return render_page(request)

    flow = _pending_oauth_flows.pop(state, None)
    if flow:
        logger.info(
            "oauth_flow_cancelled",
            account=flow.account_name,
            state=state[:8] + "...",
        )
    else:
        # Log failed cleanup (helps identify timing issues)
        pending_accounts = _get_pending_account_names()
        logger.warning(
            "oauth_cancel_unknown_state",
            state_prefix=state[:8] + "...",
            pending_accounts=pending_accounts,
        )

    return render_page(request)


@router.post("/check-capacity/{account_name}", response_class=HTMLResponse)
async def check_account_capacity(
    request: Request,
    account_name: str,
) -> HTMLResponse:
    """Check capacity for an account by making a minimal API call."""
    pool = get_pool(request)
    if not pool:
        return render_page(request, status_message="Pool not initialized")

    account = pool.get_account(account_name)
    if not account:
        return render_page(request, status_message=f"Account {account_name} not found")

    try:
        capacity = await check_capacity_async(account_name)

        # Update account capacity
        account.update_capacity(
            tokens_limit=capacity.tokens_limit,
            tokens_remaining=capacity.tokens_remaining,
            requests_limit=capacity.requests_limit,
            requests_remaining=capacity.requests_remaining,
        )

        if capacity.error:
            # If rate limited, ensure pool state reflects this before rendering
            # The middleware should have already set the correct reset time from headers
            if "rate limited" in capacity.error.lower():
                logger.info(
                    "capacity_check_rate_limited",
                    account=account_name,
                    current_state=account.state,
                    rate_limited_until=account.rate_limited_until,
                )
                # Only mark if not already rate limited (to avoid overriding the correct time)
                if account.state != "rate_limited":
                    logger.warning(
                        "capacity_check_marking_rate_limited",
                        account=account_name,
                        reason="middleware did not update state",
                    )
                    pool.mark_rate_limited(account_name)
            return render_page(request, status_message=f"Capacity check for {account_name}: {capacity.error}")

        if capacity.tokens_remaining_percent is not None:
            return render_page(
                request,
                status_message=f"Account {account_name}: {capacity.tokens_remaining_percent:.0f}% tokens remaining",
            )

        return render_page(request, status_message=f"Capacity check for {account_name} completed")

    except Exception as e:
        logger.error("capacity_check_failed", account=account_name, error=str(e))
        return render_page(request, status_message=f"Capacity check failed: {e}")


def mount_accounts_ui(app: FastAPI) -> None:
    """Mount the accounts management UI on FastAPI app at /accounts."""
    app.include_router(router)
    logger.info("accounts_ui_mounted", path="/accounts")
