"""Status endpoints for account rotation monitoring.

Provides visibility into account pool status, individual account states,
and health checks with rotation awareness.
"""

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from structlog import get_logger

from ccproxy.rotation.pool import RotationPool


logger = get_logger(__name__)

router = APIRouter(tags=["status"])


class AccountStatusResponse(BaseModel):
    """Status response for a single account."""

    name: str = Field(description="Account identifier")
    state: str = Field(description="Current state: available, rate_limited, auth_error, disabled")
    tokenExpiresAt: str = Field(description="ISO8601 timestamp of token expiration")
    tokenExpiresIn: int = Field(description="Seconds until token expiration")
    rateLimitedUntil: str | None = Field(
        default=None, description="ISO8601 timestamp when rate limit resets"
    )
    lastUsed: str | None = Field(
        default=None, description="ISO8601 timestamp of last request"
    )
    lastError: str | None = Field(default=None, description="Most recent error message")


class RotationStatusResponse(BaseModel):
    """Aggregate status response for rotation pool."""

    totalAccounts: int = Field(description="Total configured accounts")
    availableAccounts: int = Field(description="Accounts ready for requests")
    rateLimitedAccounts: int = Field(description="Accounts in rate-limit cooldown")
    authErrorAccounts: int = Field(description="Accounts needing re-authentication")
    nextAccount: str | None = Field(description="Next account in rotation order")
    accounts: list[AccountStatusResponse] = Field(description="Per-account details")


class HealthResponse(BaseModel):
    """Health check response with rotation awareness."""

    status: str = Field(description="Service health status")
    availableAccounts: int = Field(description="Number of accounts ready for requests")
    timestamp: str = Field(description="Current server timestamp")


def get_pool_from_request(request: Request) -> RotationPool:
    """Get rotation pool from app state.

    Args:
        request: FastAPI request

    Returns:
        RotationPool instance

    Raises:
        HTTPException: If pool not available
    """
    pool = getattr(request.app.state, "rotation_pool", None)
    if pool is None:
        raise HTTPException(
            status_code=503,
            detail="Rotation pool not initialized"
        )
    return pool


@router.get("/health", response_model=HealthResponse)
async def health_check(request: Request) -> HealthResponse:
    """Health check endpoint with rotation pool status.

    Returns service health and number of available accounts.
    """
    try:
        pool = get_pool_from_request(request)
        available = pool.available_count
        status = "healthy" if available > 0 else "degraded"
    except HTTPException:
        available = 0
        status = "degraded"

    return HealthResponse(
        status=status,
        availableAccounts=available,
        timestamp=datetime.now(UTC).isoformat(),
    )


@router.get("/status", response_model=RotationStatusResponse)
async def get_rotation_status(request: Request) -> RotationStatusResponse:
    """Get detailed status of the rotation pool.

    Returns counts and per-account status details.
    """
    pool = get_pool_from_request(request)
    status = pool.get_status()

    return RotationStatusResponse(
        totalAccounts=status["totalAccounts"],
        availableAccounts=status["availableAccounts"],
        rateLimitedAccounts=status["rateLimitedAccounts"],
        authErrorAccounts=status["authErrorAccounts"],
        nextAccount=status["nextAccount"],
        accounts=[
            AccountStatusResponse(**account)
            for account in status["accounts"]
        ],
    )


@router.get("/status/accounts", response_model=list[AccountStatusResponse])
async def list_account_status(request: Request) -> list[AccountStatusResponse]:
    """List status of all configured accounts."""
    pool = get_pool_from_request(request)
    status = pool.get_status()

    return [
        AccountStatusResponse(**account)
        for account in status["accounts"]
    ]


@router.get("/status/accounts/{name}", response_model=AccountStatusResponse)
async def get_account_status(request: Request, name: str) -> AccountStatusResponse:
    """Get status of a specific account.

    Args:
        name: Account name to query

    Returns:
        Account status details

    Raises:
        HTTPException: If account not found
    """
    pool = get_pool_from_request(request)
    account = pool.get_account(name)

    if account is None:
        raise HTTPException(
            status_code=404,
            detail=f"Account '{name}' not found"
        )

    status = pool._get_account_status(account)
    return AccountStatusResponse(**status)


@router.post("/status/accounts/{name}/refresh")
async def refresh_account_token(request: Request, name: str) -> dict[str, Any]:
    """Manually trigger token refresh for an account.

    Args:
        name: Account name to refresh

    Returns:
        Result of refresh operation
    """
    pool = get_pool_from_request(request)
    account = pool.get_account(name)

    if account is None:
        raise HTTPException(
            status_code=404,
            detail=f"Account '{name}' not found"
        )

    # Get refresh scheduler from app state
    scheduler = getattr(request.app.state, "refresh_scheduler", None)
    if scheduler is None:
        raise HTTPException(
            status_code=503,
            detail="Token refresh scheduler not available"
        )

    success = await scheduler.refresh_account_now(name)

    if success:
        return {
            "status": "success",
            "message": f"Token refreshed for account '{name}'",
            "account": name,
        }
    else:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to refresh token for account '{name}'"
        )


@router.post("/status/accounts/{name}/enable")
async def enable_account(request: Request, name: str) -> dict[str, Any]:
    """Manually restore an account to available state.

    Use after resolving auth errors or testing an account.

    Args:
        name: Account name to enable

    Returns:
        Result of operation
    """
    pool = get_pool_from_request(request)
    account = pool.get_account(name)

    if account is None:
        raise HTTPException(
            status_code=404,
            detail=f"Account '{name}' not found"
        )

    old_state = account.state
    pool.mark_available(name)

    return {
        "status": "success",
        "message": f"Account '{name}' enabled",
        "previousState": old_state,
        "newState": "available",
    }
