"""Pydantic-based validation utilities for the CCProxy API.

This module re-exports Pydantic's built-in validators and provides
a few custom validators for domain-specific needs.
"""

from pathlib import Path
from typing import Annotated

from pydantic import (
    EmailStr,
    Field,
    HttpUrl,
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
