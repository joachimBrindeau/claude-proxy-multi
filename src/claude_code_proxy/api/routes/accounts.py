"""OAuth account export/import API routes.

This module provides endpoints for exporting and importing OAuth account credentials
to enable migration between installation methods (Docker, Homebrew, Chocolatey, etc.).

Endpoints:
    GET  /api/accounts        - Export all OAuth accounts as JSON
    POST /api/accounts/import - Import OAuth accounts from uploaded JSON file

Security:
    All endpoints require the same authentication as the Claude Code Proxy web UI.
    All operations must be performed over HTTPS in production to protect OAuth tokens.
"""

from pathlib import Path

import structlog
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator


logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/accounts", tags=["accounts"])


# ============================================================================
# Request/Response Models
# ============================================================================


class Account(BaseModel):
    """OAuth account entity."""

    id: str = Field(..., description="Unique account identifier (UUID v4)")
    email: str = Field(..., description="User's Claude account email address")
    access_token: str = Field(..., description="OAuth access token (JWT format)")
    refresh_token: str = Field(..., description="OAuth refresh token (JWT format)")
    expires_at: int = Field(..., description="Access token expiration (Unix seconds)")
    created_at: int = Field(
        ..., description="Account creation timestamp (Unix seconds)"
    )
    updated_at: int = Field(
        ..., description="Last modification timestamp (Unix seconds)"
    )
    is_active: bool = Field(..., description="Whether account is enabled")
    metadata: dict[str, str] | None = Field(
        default=None,
        description="Optional metadata about installation context",
    )


class AccountsExport(BaseModel):
    """Response model for account export."""

    accounts: list[Account] = Field(..., description="List of all OAuth accounts")
    schema_version: str = Field(..., description="Data format version (semver)")


class AccountsImport(BaseModel):
    """Request model for account import."""

    accounts: list[Account] = Field(..., description="List of accounts to import")
    schema_version: str = Field(
        ..., description="Data format version (must be compatible)"
    )

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, value: str) -> str:
        """Validate schema version compatibility."""
        # Currently only supporting version 1.0.0
        if not value.startswith("1."):
            raise ValueError(
                f"Schema version {value} not compatible with current version 1.0.0"
            )
        return value


class ImportResult(BaseModel):
    """Response model for import operation."""

    status: str = Field(..., description="Overall import status")
    imported: int = Field(..., description="Number of new accounts imported")
    updated: int = Field(..., description="Number of existing accounts updated")
    skipped: int = Field(..., description="Number of accounts skipped")
    errors: list[dict[str, str]] = Field(
        ..., description="List of accounts that failed validation"
    )


# ============================================================================
# API Endpoints
# ============================================================================


@router.get(
    "",
    response_model=AccountsExport,
    summary="Export all accounts",
    description="Returns all OAuth accounts in JSON format for download/backup",
)
async def export_accounts() -> JSONResponse:
    """Export all OAuth accounts.

    Returns:
        JSONResponse with all accounts and schema version.

    Raises:
        HTTPException 500: If accounts.json cannot be read.
    """
    try:
        # Read accounts from storage
        accounts_file = _get_accounts_file_path()

        if not accounts_file.exists():
            # No accounts file yet - return empty list
            return JSONResponse(
                content={
                    "accounts": [],
                    "schema_version": "1.0.0",
                }
            )

        # Read existing accounts
        import json

        with accounts_file.open() as f:
            data = json.load(f)

        # Return with schema version
        return JSONResponse(
            content={
                "accounts": data.get("accounts", []),
                "schema_version": "1.0.0",
            }
        )

    except Exception as e:  # noqa: BLE001 - catch-all for file I/O errors
        logger.error("accounts_export_failed", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to read accounts.json. See server logs for details. Error: {e}",
        ) from e


@router.post(
    "/import",
    response_model=ImportResult,
    summary="Import accounts from file",
    description="Imports OAuth accounts from uploaded accounts.json file",
)
async def import_accounts(data: AccountsImport) -> ImportResult:
    """Import OAuth accounts.

    Merge Strategy (FR-027):
    - Existing emails: Update tokens and timestamps
    - New emails: Insert as new accounts
    - No deletions: Existing accounts not in import are preserved

    Args:
        data: Import payload with accounts and schema version.

    Returns:
        ImportResult with counts of imported, updated, and skipped accounts.

    Raises:
        HTTPException 400: Invalid JSON, missing schema_version, or incompatible schema.
        HTTPException 409: Duplicate emails within import data.
        HTTPException 422: Validation errors (invalid tokens, bad field formats).
        HTTPException 500: File write errors.
    """
    # Validate no duplicate emails in import data
    emails = [acc.email for acc in data.accounts]
    if len(emails) != len(set(emails)):
        duplicates = [email for email in emails if emails.count(email) > 1]
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Duplicate emails found in import data: {', '.join(set(duplicates))}",
        )

    try:
        # Read existing accounts
        accounts_file = _get_accounts_file_path()
        existing_accounts = {}

        if accounts_file.exists():
            import json

            with accounts_file.open() as f:
                existing_data = json.load(f)
                for acc in existing_data.get("accounts", []):
                    existing_accounts[acc["email"]] = acc

        # Merge accounts
        imported_count = 0
        updated_count = 0

        for account in data.accounts:
            if account.email in existing_accounts:
                # Update existing account
                existing_accounts[account.email] = account.model_dump()
                updated_count += 1
            else:
                # Add new account
                existing_accounts[account.email] = account.model_dump()
                imported_count += 1

        # Write back to file
        accounts_file.parent.mkdir(parents=True, exist_ok=True)

        import json

        with accounts_file.open("w") as f:
            json.dump(
                {
                    "accounts": list(existing_accounts.values()),
                    "schema_version": "1.0.0",
                },
                f,
                indent=2,
            )

        return ImportResult(
            status="success",
            imported=imported_count,
            updated=updated_count,
            skipped=0,
            errors=[],
        )

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:  # noqa: BLE001 - catch-all for file I/O errors
        logger.error("accounts_import_failed", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to write accounts.json. Error: {e}",
        ) from e


# ============================================================================
# Helper Functions
# ============================================================================


def _get_accounts_file_path() -> Path:
    """Get the path to the accounts.json file.

    Returns:
        Path to accounts.json configured via CCPROXY_ACCOUNTS_PATH or default.
    """
    from claude_code_proxy.rotation.startup import get_accounts_path

    return get_accounts_path(validate=False)
