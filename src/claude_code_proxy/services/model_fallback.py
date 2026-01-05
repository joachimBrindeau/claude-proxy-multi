"""Model fallback service with 403-based automatic fallback.

This module provides subscription-aware model resolution with automatic
fallback when a user doesn't have access to a specific model (403 error).

Key Features:
- Dynamic fallback: latest → next latest → next... (excluding failed)
- Per-user persistent cache of unavailable models
- X-Actual-Model response header when fallback occurs
- Configurable model providers for model list source

Architecture:
    Request: model="claude-sonnet-latest"
    → Resolve: claude-sonnet-4-5 (dynamic latest)
    → Try request to Anthropic API
    → If 403:
        a. Add claude-sonnet-4-5 to user's "unavailable" list
        b. Get next latest sonnet (excluding unavailable)
        c. Retry with claude-sonnet-4
    → Success → Add header: X-Actual-Model: claude-sonnet-4
"""

from __future__ import annotations

import asyncio
import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, TypeVar

from claude_code_proxy.core.logging import get_logger


if TYPE_CHECKING:
    from collections.abc import Awaitable

logger = get_logger(__name__)

# Type for the response from the API call
T = TypeVar("T")


class ModelProvider(str, Enum):
    """Supported model list providers."""

    ANTHROPIC = "anthropic"
    OPENROUTER = "openrouter"
    LITELLM = "litellm"


class ModelTier(str, Enum):
    """Claude model tiers."""

    SONNET = "sonnet"
    OPUS = "opus"
    HAIKU = "haiku"


@dataclass
class ModelResolutionSettings:
    """Settings for model resolution and fallback behavior."""

    # Provider for model list (where to get available models)
    provider: ModelProvider = ModelProvider.ANTHROPIC

    # Enable automatic fallback on 403
    enable_fallback: bool = True

    # Default model per tier (starting point for resolution)
    tier_defaults: dict[str, str] = field(
        default_factory=lambda: {
            "sonnet": "claude-sonnet-latest",
            "opus": "claude-opus-latest",
            "haiku": "claude-haiku-latest",
        }
    )

    # How long to remember a model is unavailable (seconds)
    # Default: 1 hour
    unavailability_cache_ttl: int = 3600


@dataclass
class CachedUnavailability:
    """Cached record of a model being unavailable for a user."""

    model: str
    timestamp: float
    error_code: int = 403


class ModelAvailabilityCache:
    """Per-user persistent cache of model availability.

    Tracks which models have returned 403 errors for each user,
    so we can skip them on future requests within the TTL.
    """

    def __init__(self, ttl_seconds: int = 3600) -> None:
        """Initialize the cache.

        Args:
            ttl_seconds: How long to remember unavailability (default: 1 hour)
        """
        self._ttl_seconds = ttl_seconds
        # user_id → model → CachedUnavailability
        self._unavailable: dict[str, dict[str, CachedUnavailability]] = {}
        self._lock = asyncio.Lock()

    async def mark_unavailable(
        self, user_id: str, model: str, error_code: int = 403
    ) -> None:
        """Mark a model as unavailable for a user.

        Args:
            user_id: User identifier
            model: Model that returned 403
            error_code: HTTP error code (default: 403)
        """
        async with self._lock:
            if user_id not in self._unavailable:
                self._unavailable[user_id] = {}

            self._unavailable[user_id][model] = CachedUnavailability(
                model=model,
                timestamp=time.time(),
                error_code=error_code,
            )
            logger.info(
                "model_marked_unavailable",
                user_id=user_id,
                model=model,
                error_code=error_code,
            )

    async def is_available(self, user_id: str, model: str) -> bool:
        """Check if a model is available for a user.

        Args:
            user_id: User identifier
            model: Model to check

        Returns:
            True if model is available (not in unavailable cache or TTL expired)
        """
        async with self._lock:
            user_cache = self._unavailable.get(user_id, {})
            cached = user_cache.get(model)

            if cached is None:
                return True

            # Check if TTL has expired
            if time.time() - cached.timestamp > self._ttl_seconds:
                # Remove expired entry
                del user_cache[model]
                if not user_cache:
                    del self._unavailable[user_id]
                return True

            return False

    async def get_unavailable_models(self, user_id: str) -> set[str]:
        """Get all unavailable models for a user.

        Args:
            user_id: User identifier

        Returns:
            Set of unavailable model names
        """
        async with self._lock:
            user_cache = self._unavailable.get(user_id, {})
            current_time = time.time()

            # Filter out expired entries
            unavailable = set()
            expired = []
            for model, cached in user_cache.items():
                if current_time - cached.timestamp > self._ttl_seconds:
                    expired.append(model)
                else:
                    unavailable.add(model)

            # Clean up expired entries
            for model in expired:
                del user_cache[model]

            return unavailable

    async def clear_user(self, user_id: str) -> None:
        """Clear all cached unavailability for a user.

        Args:
            user_id: User identifier
        """
        async with self._lock:
            self._unavailable.pop(user_id, None)

    async def clear_all(self) -> None:
        """Clear all cached unavailability."""
        async with self._lock:
            self._unavailable.clear()


# Regex pattern to extract tier from model name
# Matches: claude-sonnet-*, claude-opus-*, claude-haiku-*
TIER_PATTERN = re.compile(r"^claude-(\w+)-")


def extract_tier(model: str) -> ModelTier | None:
    """Extract the tier from a model name.

    Args:
        model: Model name (e.g., "claude-sonnet-4-5")

    Returns:
        ModelTier or None if not a recognized tier
    """
    match = TIER_PATTERN.match(model)
    if match:
        tier_str = match.group(1).lower()
        try:
            return ModelTier(tier_str)
        except ValueError:
            return None
    return None


class FallbackResolver:
    """Resolves models with 403 fallback logic.

    When a model returns 403 (permission denied), automatically
    falls back to the next available model in the same tier.
    """

    def __init__(
        self,
        availability_cache: ModelAvailabilityCache,
        settings: ModelResolutionSettings | None = None,
    ) -> None:
        """Initialize the resolver.

        Args:
            availability_cache: Cache for tracking unavailable models
            settings: Model resolution settings
        """
        self._cache = availability_cache
        self._settings = settings or ModelResolutionSettings()
        # Will be populated from model resolver
        self._models_by_tier: dict[ModelTier, list[str]] = {}

    def set_models_by_tier(self, models_by_tier: dict[ModelTier, list[str]]) -> None:
        """Set the available models by tier (sorted by version, newest first).

        Args:
            models_by_tier: Dict mapping tier to list of models (newest first)
        """
        self._models_by_tier = models_by_tier

    async def get_next_available_model(
        self, user_id: str, tier: ModelTier, exclude: set[str] | None = None
    ) -> str | None:
        """Get the next available model for a tier.

        Args:
            user_id: User identifier
            tier: Model tier to get
            exclude: Additional models to exclude (beyond cached unavailable)

        Returns:
            Next available model name, or None if none available
        """
        models = self._models_by_tier.get(tier, [])
        if not models:
            logger.warning("no_models_for_tier", tier=tier.value)
            return None

        # Get all unavailable models for this user
        unavailable = await self._cache.get_unavailable_models(user_id)
        if exclude:
            unavailable = unavailable | exclude

        # Find first available model
        for model in models:
            if model not in unavailable:
                return model

        logger.warning(
            "all_models_unavailable",
            tier=tier.value,
            user_id=user_id,
            unavailable=list(unavailable),
        )
        return None

    async def resolve_with_fallback(
        self,
        requested_model: str,
        user_id: str,
        make_request: Callable[[str], Awaitable[tuple[T, int]]],
        max_retries: int = 5,
    ) -> tuple[T, str, bool]:
        """Resolve a model with automatic 403 fallback.

        Args:
            requested_model: The model requested by the user
            user_id: User identifier for caching
            make_request: Async function that takes model name and returns
                          (response, status_code) tuple
            max_retries: Maximum fallback attempts

        Returns:
            Tuple of (response, actual_model_used, fallback_occurred)

        Raises:
            ModelUnavailableError: If no models are available after fallback
        """
        if not self._settings.enable_fallback:
            # Fallback disabled, just make the request
            response, status = await make_request(requested_model)
            return response, requested_model, False

        tier = extract_tier(requested_model)
        if tier is None:
            # Not a tiered model, can't fallback
            response, status = await make_request(requested_model)
            return response, requested_model, False

        current_model = requested_model
        attempted: set[str] = set()
        fallback_occurred = False

        for attempt in range(max_retries):
            # Check if this model is already known to be unavailable
            if not await self._cache.is_available(user_id, current_model):
                logger.debug(
                    "model_known_unavailable",
                    model=current_model,
                    user_id=user_id,
                )
                attempted.add(current_model)
                next_model = await self.get_next_available_model(
                    user_id, tier, exclude=attempted
                )
                if next_model is None:
                    raise ModelUnavailableError(
                        f"No available models in tier {tier.value} for user {user_id}"
                    )
                current_model = next_model
                fallback_occurred = True
                continue

            # Try the request
            logger.debug(
                "trying_model",
                model=current_model,
                attempt=attempt + 1,
                user_id=user_id,
            )

            response, status = await make_request(current_model)

            if status == 403:
                # Model not available for this user
                await self._cache.mark_unavailable(user_id, current_model, status)
                attempted.add(current_model)

                # Get next model
                next_model = await self.get_next_available_model(
                    user_id, tier, exclude=attempted
                )
                if next_model is None:
                    raise ModelUnavailableError(
                        f"No available models in tier {tier.value} for user {user_id}"
                    )

                logger.info(
                    "model_fallback",
                    from_model=current_model,
                    to_model=next_model,
                    user_id=user_id,
                    reason="403_permission_denied",
                )
                current_model = next_model
                fallback_occurred = True
                continue

            # Success (or non-403 error which we don't handle)
            return response, current_model, fallback_occurred

        # Exhausted retries
        raise ModelUnavailableError(
            f"Exhausted {max_retries} fallback attempts for tier {tier.value}"
        )


class ModelUnavailableError(Exception):
    """Raised when no models are available after fallback attempts."""


# Global instances
_availability_cache: ModelAvailabilityCache | None = None
_fallback_resolver: FallbackResolver | None = None
_settings: ModelResolutionSettings | None = None


def get_availability_cache() -> ModelAvailabilityCache | None:
    """Get the global availability cache instance."""
    return _availability_cache


def get_fallback_resolver() -> FallbackResolver | None:
    """Get the global fallback resolver instance."""
    return _fallback_resolver


def get_model_resolution_settings() -> ModelResolutionSettings | None:
    """Get the global model resolution settings."""
    return _settings


def initialize_model_fallback(
    settings: ModelResolutionSettings | None = None,
) -> tuple[ModelAvailabilityCache, FallbackResolver]:
    """Initialize the model fallback system.

    Args:
        settings: Model resolution settings (uses defaults if None)

    Returns:
        Tuple of (availability_cache, fallback_resolver)
    """
    global _availability_cache, _fallback_resolver, _settings

    _settings = settings or ModelResolutionSettings()
    _availability_cache = ModelAvailabilityCache(
        ttl_seconds=_settings.unavailability_cache_ttl
    )
    _fallback_resolver = FallbackResolver(
        availability_cache=_availability_cache,
        settings=_settings,
    )

    logger.info(
        "model_fallback_initialized",
        provider=_settings.provider.value,
        enable_fallback=_settings.enable_fallback,
        ttl_seconds=_settings.unavailability_cache_ttl,
    )

    return _availability_cache, _fallback_resolver


def shutdown_model_fallback() -> None:
    """Shutdown and cleanup the model fallback system."""
    global _availability_cache, _fallback_resolver, _settings

    _availability_cache = None
    _fallback_resolver = None
    _settings = None

    logger.info("model_fallback_shutdown")


__all__ = [
    "FallbackResolver",
    "ModelAvailabilityCache",
    "ModelProvider",
    "ModelResolutionSettings",
    "ModelTier",
    "ModelUnavailableError",
    "extract_tier",
    "get_availability_cache",
    "get_fallback_resolver",
    "get_model_resolution_settings",
    "initialize_model_fallback",
    "shutdown_model_fallback",
]
