"""API key authentication configuration."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class PublicRoutesConfig:
    """Configuration for routes that don't require API key authentication."""

    exact_matches: frozenset[str] = field(
        default_factory=lambda: frozenset(
            {
                "/health",
                "/docs",
                "/openapi.json",
                "/redoc",
            }
        )
    )

    prefixes: tuple[str, ...] = field(
        default_factory=lambda: (
            "/static/",
            "/_next/",
        )
    )

    def is_public(self, path: str) -> bool:
        """Check if a path is public (doesn't require authentication).

        Args:
            path: Request path to check

        Returns:
            True if path is public, False otherwise

        """
        # Check exact matches
        if path in self.exact_matches:
            return True

        # Check prefixes
        return any(path.startswith(prefix) for prefix in self.prefixes)


# Default public routes configuration
DEFAULT_PUBLIC_ROUTES = PublicRoutesConfig()
