"""Minimal request context for tracking request IDs.

This is a simplified replacement for the full observability context.
Only provides request ID tracking - no metrics, no storage, no logging.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RequestContext:
    """Minimal request context holding just the request ID and basic metadata."""

    request_id: str
    method: str = ""
    path: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def add_metadata(self, **kwargs: Any) -> None:
        """Add metadata to the context (no-op for compatibility)."""
        self.metadata.update(kwargs)

    def get_log_timestamp_prefix(self) -> str:
        """Return empty string for compatibility."""
        return ""
