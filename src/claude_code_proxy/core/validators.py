"""Pydantic-based validation utilities for the CCProxy API.

This module re-exports Pydantic's built-in validators and provides
a few custom validators for domain-specific needs.
"""

from pathlib import Path
from typing import Annotated

from pydantic import (
    BaseModel,
    EmailStr,
    Field,
    HttpUrl,
    field_validator,
)
from pydantic import (
    ValidationError as PydanticValidationError,
)


__all__ = [
    # Pydantic types re-exported for convenience
    "EmailStr",
    "HttpUrl",
    "ValidationError",
    # Custom annotated types
    "Port",
    "PositiveTimeout",
    "NonEmptyStr",
    # Utility functions
    "parse_comma_separated",
    "validate_path",
    # OAuth account models for import/export
    "Account",
    "AccountsExport",
    "AccountsImport",
    "ImportResult",
]


# Alias Pydantic's ValidationError for backward compatibility
ValidationError = PydanticValidationError


# Custom annotated types using Pydantic Field constraints
Port = Annotated[int, Field(ge=1, le=65535, description="TCP/UDP port number")]
PositiveTimeout = Annotated[float, Field(gt=0, description="Timeout value in seconds")]
NonEmptyStr = Annotated[str, Field(min_length=1, description="Non-empty string")]


def parse_comma_separated(
    value: str | list[str],
    strip: bool = True,
    filter_empty: bool = True,
    max_items: int | None = None,
) -> list[str]:
    """Parse comma-separated string into list of values.

    This is a utility function for parsing config values that may
    be provided as comma-separated strings or lists.

    Args:
        value: Comma-separated string or list
        strip: Whether to strip whitespace from each item
        filter_empty: Whether to filter out empty strings
        max_items: Maximum number of items allowed (default: None, no limit)

    Returns:
        List of parsed values

    Raises:
        ValidationError: If max_items is exceeded
    """
    if isinstance(value, list):
        items = value
    else:
        items = value.split(",")

    # Security: Limit number of items to prevent abuse
    if max_items is not None and len(items) > max_items:
        raise ValidationError(
            f"Too many items: got {len(items)}, maximum is {max_items}"
        )

    if strip:
        items = [item.strip() for item in items]

    if filter_empty:
        items = [item for item in items if item]

    return items


def validate_path(path: str | Path, must_exist: bool = True) -> Path:
    """Validate file system path.

    Args:
        path: Path to validate
        must_exist: Whether the path must exist

    Returns:
        The validated Path object

    Raises:
        ValidationError: If path is invalid
    """
    if isinstance(path, str):
        path = Path(path)
    elif not isinstance(path, Path):
        raise ValidationError("Path must be a string or Path object")

    if must_exist and not path.exists():
        raise ValidationError(f"Path does not exist: {path}")

    return path.resolve()


# OAuth Account Import/Export Models


class Account(BaseModel):
    """OAuth account entity for import/export.

    Represents a single Claude account with OAuth tokens and metadata.
    Used for migrating accounts between installations.
    """

    id: str = Field(..., description="Unique account identifier (UUID v4)")
    email: EmailStr = Field(..., description="User's Claude account email address")
    access_token: str = Field(..., description="OAuth access token (JWT format)")
    refresh_token: str = Field(..., description="OAuth refresh token (JWT format)")
    expires_at: int = Field(
        ..., description="Access token expiration (Unix seconds)", gt=0
    )
    created_at: int = Field(
        ..., description="Account creation timestamp (Unix seconds)", gt=0
    )
    updated_at: int = Field(
        ..., description="Last modification timestamp (Unix seconds)", gt=0
    )
    is_active: bool = Field(default=True, description="Whether account is enabled")
    metadata: dict[str, str] | None = Field(
        default=None, description="Optional metadata (key-value pairs)"
    )

    @field_validator("id")
    @classmethod
    def validate_uuid(cls, value: str) -> str:
        """Validate that id is a valid UUID v4 format."""
        import uuid

        try:
            uuid_obj = uuid.UUID(value, version=4)
            if str(uuid_obj) != value:
                raise ValueError("Invalid UUID format")
            return value
        except (ValueError, AttributeError) as e:
            raise ValueError(f"Invalid UUID v4: {e}") from e

    @field_validator("access_token", "refresh_token")
    @classmethod
    def validate_token_format(cls, value: str) -> str:
        """Validate token is non-empty and looks like JWT."""
        if not value or not value.strip():
            raise ValueError("Token cannot be empty")
        # JWT tokens have 3 parts separated by dots
        if value.count(".") != 2:
            raise ValueError("Token must be in JWT format (3 parts separated by dots)")
        return value


class AccountsExport(BaseModel):
    """Export format for OAuth accounts.

    Contains a list of accounts and schema version for compatibility checking.
    """

    accounts: list[Account] = Field(..., description="List of OAuth accounts to export")
    schema_version: str = Field(
        default="1.0.0", description="Schema version for compatibility (semver)"
    )

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, value: str) -> str:
        """Validate schema version is 1.* format."""
        if not value.startswith("1."):
            raise ValueError(
                f"Unsupported schema version: {value} (only 1.* is supported)"
            )
        # Basic semver validation (1.x.y)
        parts = value.split(".")
        if len(parts) != 3:
            raise ValueError(f"Invalid schema version format: {value} (expected 1.x.y)")
        try:
            int(parts[1])  # minor version
            int(parts[2])  # patch version
        except ValueError as e:
            raise ValueError(f"Invalid schema version: {value}") from e
        return value

    @field_validator("accounts")
    @classmethod
    def validate_unique_emails(cls, accounts: list[Account]) -> list[Account]:
        """Ensure no duplicate email addresses in export."""
        emails = [acc.email for acc in accounts]
        if len(emails) != len(set(emails)):
            raise ValueError("Duplicate email addresses found in accounts list")
        return accounts


class AccountsImport(BaseModel):
    """Import format for OAuth accounts.

    Same structure as export, validates accounts before import.
    """

    accounts: list[Account] = Field(..., description="List of OAuth accounts to import")
    schema_version: str = Field(
        default="1.0.0", description="Schema version for compatibility (semver)"
    )

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, value: str) -> str:
        """Validate schema version is 1.* format."""
        if not value.startswith("1."):
            raise ValueError(
                f"Unsupported schema version: {value} (only 1.* is supported)"
            )
        parts = value.split(".")
        if len(parts) != 3:
            raise ValueError(f"Invalid schema version format: {value} (expected 1.x.y)")
        try:
            int(parts[1])
            int(parts[2])
        except ValueError as e:
            raise ValueError(f"Invalid schema version: {value}") from e
        return value

    @field_validator("accounts")
    @classmethod
    def validate_unique_emails(cls, accounts: list[Account]) -> list[Account]:
        """Ensure no duplicate email addresses in import."""
        emails = [acc.email for acc in accounts]
        if len(emails) != len(set(emails)):
            raise ValueError("Duplicate email addresses found in accounts list")
        return accounts


class ImportResult(BaseModel):
    """Result of account import operation.

    Provides detailed statistics about import success/failure.
    """

    imported: int = Field(..., description="Number of new accounts imported", ge=0)
    updated: int = Field(..., description="Number of existing accounts updated", ge=0)
    skipped: int = Field(
        ..., description="Number of accounts skipped (unchanged)", ge=0
    )
    errors: int = Field(default=0, description="Number of accounts with errors", ge=0)
    message: str = Field(
        default="Import completed successfully", description="Status message"
    )
