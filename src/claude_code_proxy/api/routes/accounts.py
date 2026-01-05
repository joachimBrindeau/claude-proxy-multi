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
from typing import Any

import orjson
import structlog
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse

# Import models from validators to avoid duplication
from claude_code_proxy.core.validators import (
    AccountsExport,
    AccountsImport,
    ImportResult,
)


logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/accounts", tags=["accounts"])

# Schema version for account export/import format
ACCOUNTS_SCHEMA_VERSION = "1.0.0"


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
                    "schema_version": ACCOUNTS_SCHEMA_VERSION,
                }
            )

        # Read existing accounts using orjson (faster than stdlib json)
        data = orjson.loads(accounts_file.read_bytes())

        # Return with schema version
        return JSONResponse(
            content={
                "accounts": data.get("accounts", []),
                "schema_version": ACCOUNTS_SCHEMA_VERSION,
            }
        )

    except Exception as e:
        logger.exception("accounts_export_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to read accounts. See server logs for details.",
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
        existing_accounts: dict[str, dict[str, Any]] = {}

        if accounts_file.exists():
            existing_data = orjson.loads(accounts_file.read_bytes())
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

        # Write back to file using orjson (faster, with pretty printing)
        accounts_file.parent.mkdir(parents=True, exist_ok=True)
        accounts_file.write_bytes(
            orjson.dumps(
                {
                    "accounts": list(existing_accounts.values()),
                    "schema_version": ACCOUNTS_SCHEMA_VERSION,
                },
                option=orjson.OPT_INDENT_2,
            )
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
    except Exception as e:
        logger.exception("accounts_import_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to write accounts. See server logs for details.",
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
