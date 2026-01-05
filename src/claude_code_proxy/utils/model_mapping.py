"""Claude model mapping utilities.

This module provides a single source of truth for Claude model mappings,
handling Claude aliases → canonical Claude models resolution.

For "latest" aliases (e.g., claude-sonnet-latest), we use:
1. Dynamic resolution via ModelResolver (queries Anthropic's /v1/models API)
2. Fallback to Anthropic's dynamic aliases (e.g., claude-sonnet-4-5)

See: https://docs.anthropic.com/en/docs/about-claude/models/overview
"""

from __future__ import annotations

import re


# Anthropic's dynamic aliases (auto-update to latest snapshots)
# These are the recommended way to always get the latest version
DYNAMIC_ALIASES = {
    "claude-sonnet-4-5",
    "claude-opus-4-5",
    "claude-haiku-4-5",
    "claude-sonnet-4",
    "claude-opus-4",
}

# Claude model aliases → canonical Claude models
# For dynamic aliases, we map to Anthropic's auto-updating aliases
MODEL_MAPPING: dict[str, str] = {
    # ==========================================================================
    # LATEST ALIASES - Map to Anthropic's dynamic aliases (auto-update)
    # These don't need manual updates when new snapshots are released
    # ==========================================================================
    "claude-sonnet-latest": "claude-sonnet-4-5",
    "claude-opus-latest": "claude-opus-4-5",
    "claude-haiku-latest": "claude-haiku-4-5",
    # ==========================================================================
    # CLAUDE 4.5 MODELS (current flagship - Nov 2025)
    # ==========================================================================
    # Dynamic aliases (pass through - Anthropic resolves to latest snapshot)
    "claude-sonnet-4-5": "claude-sonnet-4-5",
    "claude-opus-4-5": "claude-opus-4-5",
    "claude-haiku-4-5": "claude-haiku-4-5",
    # Specific snapshots (for pinned versions)
    "claude-sonnet-4-5-20250929": "claude-sonnet-4-5-20250929",
    "claude-opus-4-5-20251101": "claude-opus-4-5-20251101",
    "claude-haiku-4-5-20251001": "claude-haiku-4-5-20251001",
    # ==========================================================================
    # CLAUDE 4 MODELS (May 2025)
    # ==========================================================================
    "claude-sonnet-4": "claude-sonnet-4",
    "claude-opus-4": "claude-opus-4",
    "claude-sonnet-4-20250514": "claude-sonnet-4-20250514",
    "claude-opus-4-20250514": "claude-opus-4-20250514",
    # ==========================================================================
    # CLAUDE 3.7 MODELS
    # ==========================================================================
    "claude-3-7-sonnet-20250219": "claude-3-7-sonnet-20250219",
    "claude-3-7-sonnet-latest": "claude-3-7-sonnet-20250219",
    # ==========================================================================
    # CLAUDE 3.5 MODELS
    # ==========================================================================
    "claude-3-5-sonnet-latest": "claude-3-5-sonnet-20241022",
    "claude-3-5-sonnet-20240620": "claude-3-5-sonnet-20240620",
    "claude-3-5-sonnet-20241022": "claude-3-5-sonnet-20241022",
    "claude-3-5-haiku-latest": "claude-3-5-haiku-20241022",
    "claude-3-5-haiku-20241022": "claude-3-5-haiku-20241022",
    # ==========================================================================
    # CLAUDE 3 MODELS (legacy - some deprecated)
    # ==========================================================================
    "claude-3-opus": "claude-3-opus-20240229",
    "claude-3-opus-20240229": "claude-3-opus-20240229",
    "claude-3-sonnet": "claude-3-sonnet-20240229",
    "claude-3-sonnet-20240229": "claude-3-sonnet-20240229",
    "claude-3-haiku": "claude-3-haiku-20240307",
    "claude-3-haiku-20240307": "claude-3-haiku-20240307",
}


def map_model_to_claude(model_name: str) -> str:
    """Map a model name to its canonical Claude model name.

    This function handles:
    - Stripping provider prefixes (openai/, anthropic/, claude/)
    - Dynamic resolution for "latest" aliases via ModelResolver
    - Claude aliases → canonical Claude names
    - Pass-through for Anthropic's dynamic aliases and unknown models

    For "latest" aliases (e.g., claude-sonnet-latest), we try:
    1. Dynamic resolution via ModelResolver (queries Anthropic's /v1/models API)
    2. Fallback to static MODEL_MAPPING

    Args:
        model_name: Model identifier (Claude or alias)

    Returns:
        Canonical Claude model identifier

    """
    # Strip common provider prefixes (used by LiteLLM and other gateways)
    for prefix in ("openai/", "anthropic/", "claude/"):
        if model_name.startswith(prefix):
            model_name = model_name[len(prefix) :]
            break

    # Try dynamic resolution for "latest" aliases first
    if is_latest_alias(model_name):
        resolved = resolve_latest_alias(model_name)
        if resolved != model_name:
            return resolved

    # Direct mapping from static table (handles Claude aliases)
    claude_model = MODEL_MAPPING.get(model_name)
    if claude_model:
        return claude_model

    # If it's already a Claude model, pass through unchanged
    # This handles Anthropic's dynamic aliases like claude-sonnet-4-5
    if model_name.startswith("claude-"):
        return model_name

    # For unknown models, pass through unchanged
    return model_name


# Regex pattern to identify "latest" aliases (e.g., claude-sonnet-latest)
LATEST_ALIAS_PATTERN = re.compile(r"^claude-(\w+)-latest$")


def is_latest_alias(model_name: str) -> bool:
    """Check if a model name is a "latest" alias.

    Args:
        model_name: Model identifier to check

    Returns:
        True if the model is a latest alias (e.g., claude-sonnet-latest)

    """
    return bool(LATEST_ALIAS_PATTERN.match(model_name))


def resolve_latest_alias(model_name: str) -> str:
    """Resolve a "latest" alias to the actual latest model.

    Uses the ModelResolver if available, otherwise returns the original alias.

    Args:
        model_name: Latest alias (e.g., claude-sonnet-latest)

    Returns:
        Resolved model ID, or original alias if resolution fails

    """
    # Import here to avoid circular imports
    from claude_code_proxy.services.model_resolver import get_model_resolver

    resolver = get_model_resolver()
    if resolver:
        return resolver.resolve(model_name)

    # Fallback to static mapping
    return MODEL_MAPPING.get(model_name, model_name)


def is_dynamic_alias(model_name: str) -> bool:
    """Check if a model name is an Anthropic dynamic alias.

    Dynamic aliases like claude-sonnet-4-5 automatically point to
    the latest snapshot and don't need manual updates.

    Args:
        model_name: Model identifier to check

    Returns:
        True if the model is a dynamic alias

    """
    return model_name in DYNAMIC_ALIASES


def get_claude_aliases_mapping() -> dict[str, str]:
    """Get mapping of Claude aliases to canonical Claude names.

    Returns:
        Dictionary mapping Claude aliases to canonical model names

    """
    return MODEL_MAPPING.copy()


def get_supported_claude_models() -> list[str]:
    """Get list of supported canonical Claude models.

    Returns:
        Sorted list of unique canonical Claude model names

    """
    return sorted(set(MODEL_MAPPING.values()))


def is_claude_model(model_name: str) -> bool:
    """Check if a model name is a Claude model (canonical or alias).

    Args:
        model_name: Model identifier to check

    Returns:
        True if the model is a Claude model, False otherwise

    """
    return model_name.startswith("claude-") or model_name in MODEL_MAPPING


def get_canonical_model_name(model_name: str) -> str:
    """Get the canonical name for a model.

    Args:
        model_name: Model name (possibly an alias)

    Returns:
        Canonical model name

    """
    return map_model_to_claude(model_name)


__all__ = [
    "DYNAMIC_ALIASES",
    "LATEST_ALIAS_PATTERN",
    "MODEL_MAPPING",
    "get_canonical_model_name",
    "get_claude_aliases_mapping",
    "get_supported_claude_models",
    "is_claude_model",
    "is_dynamic_alias",
    "is_latest_alias",
    "map_model_to_claude",
    "resolve_latest_alias",
]
