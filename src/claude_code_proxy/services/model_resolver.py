"""Dynamic model resolver for Claude model aliases.

This module provides runtime resolution of model aliases like `claude-sonnet-latest`
to the actual latest model ID by querying the Anthropic Models API.

Resolution strategy:
1. Parse `claude-{tier}-latest` to extract tier (sonnet, opus, haiku)
2. Query Anthropic's /v1/models API to get all available models
3. Filter models matching `claude-{tier}-*` pattern
4. Sort by version number (highest first)
5. Return the model with the highest version number

Refresh strategy:
- On startup: Fetch and cache model mappings
- Periodic refresh: Every 15 minutes
- Fallback: Use cached values if API unavailable
"""

from __future__ import annotations

import asyncio
import re
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import httpx
import structlog

from claude_code_proxy.exceptions import ModelResolutionError


if TYPE_CHECKING:
    from claude_code_proxy.services.credentials.manager import CredentialsManager


logger = structlog.get_logger(__name__)

# Regex pattern to extract tier from model alias (e.g., "claude-sonnet-latest" -> "sonnet")
TIER_PATTERN = re.compile(r"^claude-(\w+)-latest$")

# Regex pattern to parse model IDs (e.g., "claude-sonnet-4-5-20250929")
# Matches: claude-{tier}-{major}[-{minor}][-{date}]
MODEL_PATTERN = re.compile(
    r"^claude-(?P<tier>\w+)-(?P<major>\d+)(?:-(?P<minor>\d+))?(?:-(?P<date>\d{8}))?$"
)

# Default refresh interval in seconds (15 minutes)
DEFAULT_REFRESH_INTERVAL_SECONDS = 900

# Fallback mappings if API is unavailable
FALLBACK_MAPPINGS: dict[str, str] = {
    "sonnet": "claude-sonnet-4-5",
    "opus": "claude-opus-4-5",
    "haiku": "claude-haiku-4-5",
}


class ModelVersion:
    """Parsed model version for comparison."""

    def __init__(
        self,
        model_id: str,
        tier: str,
        major: int,
        minor: int | None = None,
        date: str | None = None,
    ) -> None:
        """Initialize model version.

        Args:
            model_id: Full model identifier
            tier: Model tier (sonnet, opus, haiku)
            major: Major version number
            minor: Minor version number (optional)
            date: Release date string YYYYMMDD (optional)

        """
        self.model_id = model_id
        self.tier = tier
        self.major = major
        self.minor = minor
        self.date = date

    @classmethod
    def parse(cls, model_id: str) -> ModelVersion | None:
        """Parse a model ID into version components.

        Args:
            model_id: Model identifier to parse

        Returns:
            ModelVersion if successfully parsed, None otherwise

        """
        match = MODEL_PATTERN.match(model_id)
        if not match:
            return None

        return cls(
            model_id=model_id,
            tier=match.group("tier"),
            major=int(match.group("major")),
            minor=int(match.group("minor")) if match.group("minor") else None,
            date=match.group("date"),
        )

    def version_tuple(self) -> tuple[int, int, str]:
        """Get version as comparable tuple.

        Returns:
            Tuple of (major, minor, date) for comparison
            Minor defaults to 0 if not present
            Date defaults to empty string if not present

        """
        return (
            self.major,
            self.minor or 0,
            self.date or "",
        )

    def __lt__(self, other: ModelVersion) -> bool:
        """Compare versions (for sorting)."""
        return self.version_tuple() < other.version_tuple()

    def __eq__(self, other: object) -> bool:
        """Check version equality."""
        if not isinstance(other, ModelVersion):
            return NotImplemented
        return self.version_tuple() == other.version_tuple()

    def __repr__(self) -> str:
        """String representation."""
        return f"ModelVersion({self.model_id})"


class ModelResolver:
    """Dynamic resolver for Claude model aliases.

    Resolves aliases like `claude-sonnet-latest` to the actual latest
    model ID by querying the Anthropic Models API.
    """

    def __init__(
        self,
        credentials_manager: CredentialsManager | None = None,
        refresh_interval_seconds: float = DEFAULT_REFRESH_INTERVAL_SECONDS,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        """Initialize the model resolver.

        Args:
            credentials_manager: Manager for OAuth credentials (optional)
            refresh_interval_seconds: Interval between cache refreshes
            http_client: HTTP client for API requests (optional)

        """
        self._credentials_manager = credentials_manager
        self._refresh_interval_seconds = refresh_interval_seconds
        self._http_client = http_client
        self._owns_http_client = http_client is None

        # Cache: tier -> latest model ID
        self._cache: dict[str, str] = {}
        # Full cache: tier -> list of models sorted by version (newest first)
        self._tier_models: dict[str, list[str]] = {}
        self._last_refresh: datetime | None = None
        self._refresh_lock = asyncio.Lock()
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the resolver by fetching initial model data.

        Should be called during application startup.
        """
        if self._initialized:
            return

        try:
            await self.refresh()
            self._initialized = True
            logger.info(
                "model_resolver_initialized",
                cached_tiers=list(self._cache.keys()),
            )
        except (httpx.HTTPError, ModelResolutionError) as e:
            # Network or resolution errors during initialization
            logger.warning(
                "model_resolver_init_failed",
                error=str(e),
                fallback="using_defaults",
            )
            # Use fallback mappings
            self._cache = FALLBACK_MAPPINGS.copy()
            # Build fallback tier models (single model per tier)
            self._tier_models = {
                tier: [model] for tier, model in FALLBACK_MAPPINGS.items()
            }
            self._initialized = True

    async def close(self) -> None:
        """Clean up resources."""
        if self._owns_http_client and self._http_client:
            await self._http_client.aclose()
            self._http_client = None

    def resolve(self, alias: str) -> str:
        """Resolve a model alias to its actual model ID.

        Args:
            alias: Model alias (e.g., "claude-sonnet-latest")

        Returns:
            Resolved model ID, or original alias if not resolvable

        """
        match = TIER_PATTERN.match(alias)
        if not match:
            return alias

        tier = match.group(1)

        # Check cache
        if tier in self._cache:
            resolved = self._cache[tier]
            logger.debug(
                "model_resolved_from_cache",
                alias=alias,
                resolved=resolved,
            )
            return resolved

        # Check fallback
        if tier in FALLBACK_MAPPINGS:
            resolved = FALLBACK_MAPPINGS[tier]
            logger.debug(
                "model_resolved_from_fallback",
                alias=alias,
                resolved=resolved,
            )
            return resolved

        # Unknown tier, return original
        logger.debug(
            "model_alias_unknown",
            alias=alias,
            tier=tier,
        )
        return alias

    async def refresh(self) -> None:
        """Refresh the model cache by querying the Anthropic API."""
        async with self._refresh_lock:
            try:
                models = await self._fetch_models()
                if not models:
                    logger.warning("model_fetch_empty_response")
                    return

                # Parse and group models by tier
                tier_models: dict[str, list[ModelVersion]] = {}
                for model_id in models:
                    version = ModelVersion.parse(model_id)
                    if version:
                        if version.tier not in tier_models:
                            tier_models[version.tier] = []
                        tier_models[version.tier].append(version)

                # Find latest model for each tier and build sorted lists
                new_cache: dict[str, str] = {}
                new_tier_models: dict[str, list[str]] = {}
                for tier, versions in tier_models.items():
                    if versions:
                        # Sort by version (highest first)
                        versions.sort(reverse=True)
                        latest = versions[0]
                        # Store all models sorted (newest first) for fallback
                        new_tier_models[tier] = [v.model_id for v in versions]
                        # Use dynamic alias if available (e.g., claude-sonnet-4-5 instead of dated snapshot)
                        # Dynamic aliases don't have dates
                        dynamic_alias = next(
                            (v for v in versions if v.date is None),
                            None,
                        )
                        if dynamic_alias:
                            new_cache[tier] = dynamic_alias.model_id
                        else:
                            new_cache[tier] = latest.model_id
                        logger.debug(
                            "tier_latest_resolved",
                            tier=tier,
                            model=new_cache[tier],
                            candidates=len(versions),
                        )

                self._cache = new_cache
                self._tier_models = new_tier_models
                self._last_refresh = datetime.now(UTC)

                logger.info(
                    "model_cache_refreshed",
                    tiers=list(new_cache.keys()),
                    models=list(new_cache.values()),
                )

            except (httpx.HTTPError, ValueError, KeyError, TypeError) as e:
                # Network errors, JSON parsing issues, or unexpected response format
                logger.exception(
                    "model_refresh_failed",
                    error=str(e),
                    error_type=type(e).__name__,
                )
                raise ModelResolutionError(f"Failed to refresh models: {e}") from e

    async def _fetch_models(self) -> list[str]:
        """Fetch available models from Anthropic API.

        Returns:
            List of model IDs

        """
        # Create HTTP client if needed
        if self._http_client is None:
            self._http_client = httpx.AsyncClient()

        # Get access token
        token = await self._get_access_token()
        if not token:
            logger.warning("model_fetch_no_token")
            return []

        # Fetch models from Anthropic API
        headers = {
            "Authorization": f"Bearer {token}",
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }

        try:
            response = await self._http_client.get(
                "https://api.anthropic.com/v1/models",
                headers=headers,
                timeout=30.0,
            )
            response.raise_for_status()

            data = response.json()

            # Extract model IDs from response
            # API returns {"data": [{"id": "model-id", ...}, ...]}
            models = data.get("data", [])
            model_ids = [
                m.get("id") for m in models if m.get("id", "").startswith("claude-")
            ]

            logger.debug(
                "models_fetched",
                count=len(model_ids),
            )
            return model_ids

        except httpx.HTTPStatusError as e:
            logger.exception(
                "model_api_error",
                status_code=e.response.status_code,
                error=str(e),
            )
            raise

    async def _get_access_token(self) -> str | None:
        """Get access token for API authentication.

        The Anthropic Models API requires an API key, not OAuth tokens.
        First checks for ANTHROPIC_API_KEY environment variable,
        then falls back to OAuth credentials (which may not work).

        Returns:
            Access token string, or None if unavailable

        """
        import os

        # Prefer API key from environment (Models API requires API key, not OAuth)
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if api_key:
            logger.debug("model_resolver_using_api_key")
            return api_key

        # Fall back to OAuth credentials (may not work for Models API)
        if self._credentials_manager is None:
            logger.debug("model_resolver_no_credentials_manager")
            return None

        try:
            token = await self._credentials_manager.get_access_token()
            logger.debug(
                "model_resolver_using_oauth",
                note="OAuth may not work for Models API",
            )
            return token
        except (ValueError, RuntimeError, OSError) as e:
            # Credential retrieval errors
            logger.warning(
                "model_resolver_token_failed",
                error=str(e),
            )
            return None

    def get_cached_mappings(self) -> dict[str, str]:
        """Get current cached tier-to-model mappings.

        Returns:
            Dictionary mapping tier names to model IDs

        """
        return self._cache.copy()

    def get_models_by_tier(self) -> dict[str, list[str]]:
        """Get all models grouped by tier, sorted by version (newest first).

        Returns:
            Dictionary mapping tier names to lists of model IDs

        """
        return self._tier_models.copy()

    def get_tier_models(self, tier: str) -> list[str]:
        """Get all models for a specific tier, sorted by version (newest first).

        Args:
            tier: Model tier (e.g., "sonnet", "opus", "haiku")

        Returns:
            List of model IDs for the tier, or empty list if tier unknown

        """
        return self._tier_models.get(tier, [])

    def is_stale(self) -> bool:
        """Check if the cache is stale and needs refresh.

        Returns:
            True if cache needs refresh

        """
        if self._last_refresh is None:
            return True

        age = (datetime.now(UTC) - self._last_refresh).total_seconds()
        return age > self._refresh_interval_seconds

    @property
    def last_refresh(self) -> datetime | None:
        """Get the timestamp of the last successful refresh."""
        return self._last_refresh

    @property
    def is_initialized(self) -> bool:
        """Check if the resolver has been initialized."""
        return self._initialized


# Global resolver instance (initialized during startup)
_resolver: ModelResolver | None = None


def get_model_resolver() -> ModelResolver | None:
    """Get the global model resolver instance.

    Returns:
        ModelResolver instance if initialized, None otherwise

    """
    return _resolver


def set_model_resolver(resolver: ModelResolver | None) -> None:
    """Set the global model resolver instance.

    Args:
        resolver: ModelResolver instance to set, or None to clear

    """
    global _resolver
    _resolver = resolver


async def resolve_model_alias(alias: str) -> str:
    """Resolve a model alias using the global resolver.

    Convenience function for resolving model aliases without
    direct access to the resolver instance.

    Args:
        alias: Model alias to resolve

    Returns:
        Resolved model ID, or original alias if resolver not available

    """
    resolver = get_model_resolver()
    if resolver:
        return resolver.resolve(alias)
    return alias


__all__ = [
    "DEFAULT_REFRESH_INTERVAL_SECONDS",
    "FALLBACK_MAPPINGS",
    "TIER_PATTERN",
    "ModelResolver",
    "ModelVersion",
    "get_model_resolver",
    "resolve_model_alias",
    "set_model_resolver",
]
