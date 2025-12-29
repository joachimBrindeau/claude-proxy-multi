"""Claude model mapping utilities.

This module provides a single source of truth for Claude model mappings,
handling Claude aliases → canonical Claude models resolution.
"""

from __future__ import annotations


# Claude model aliases → canonical Claude models
MODEL_MAPPING: dict[str, str] = {
    # Claude 4 models
    "claude-opus-4-20250514": "claude-opus-4-20250514",
    "claude-sonnet-4-20250514": "claude-sonnet-4-20250514",
    # Claude 3.7 models
    "claude-3-7-sonnet-20250219": "claude-3-7-sonnet-20250219",
    "claude-3-7-sonnet-latest": "claude-3-7-sonnet-20250219",
    # Claude 3.5 models
    "claude-3-5-sonnet-latest": "claude-3-5-sonnet-20241022",
    "claude-3-5-sonnet-20240620": "claude-3-5-sonnet-20240620",
    "claude-3-5-sonnet-20241022": "claude-3-5-sonnet-20241022",
    "claude-3-5-haiku-latest": "claude-3-5-haiku-20241022",
    "claude-3-5-haiku-20241022": "claude-3-5-haiku-20241022",
    # Claude 3 models
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
    - Claude aliases → canonical Claude names
    - Pass-through for unknown models

    Args:
        model_name: Model identifier (Claude or alias)

    Returns:
        Canonical Claude model identifier
    """
    # Direct mapping first (handles Claude aliases)
    claude_model = MODEL_MAPPING.get(model_name)
    if claude_model:
        return claude_model

    # If it's already a Claude model, pass through unchanged
    if model_name.startswith("claude-"):
        return model_name

    # For unknown models, pass through unchanged
    return model_name


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
    "MODEL_MAPPING",
    "map_model_to_claude",
    "get_claude_aliases_mapping",
    "get_supported_claude_models",
    "is_claude_model",
    "get_canonical_model_name",
]
