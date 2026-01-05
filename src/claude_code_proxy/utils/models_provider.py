"""Shared models provider for CCProxy API Server.

This module provides a centralized source for all available Claude models.
"""

from __future__ import annotations

from typing import Any

from claude_code_proxy.utils.model_mapping import get_supported_claude_models


def get_anthropic_models() -> list[dict[str, Any]]:
    """Get list of Anthropic Claude models with metadata.

    Returns:
        List of Anthropic model entries with type, id, display_name, and created_at fields

    """
    # Model display names mapping
    display_names = {
        "claude-opus-4-20250514": "Claude Opus 4",
        "claude-sonnet-4-20250514": "Claude Sonnet 4",
        "claude-3-7-sonnet-20250219": "Claude Sonnet 3.7",
        "claude-3-5-sonnet-20241022": "Claude Sonnet 3.5 (New)",
        "claude-3-5-haiku-20241022": "Claude Haiku 3.5",
        "claude-3-5-haiku-latest": "Claude Haiku 3.5",
        "claude-3-5-sonnet-20240620": "Claude Sonnet 3.5 (Old)",
        "claude-3-haiku-20240307": "Claude Haiku 3",
        "claude-3-opus-20240229": "Claude Opus 3",
    }

    # Model creation timestamps
    timestamps = {
        "claude-opus-4-20250514": 1747526400,  # 2025-05-22
        "claude-sonnet-4-20250514": 1747526400,  # 2025-05-22
        "claude-3-7-sonnet-20250219": 1740268800,  # 2025-02-24
        "claude-3-5-sonnet-20241022": 1729555200,  # 2024-10-22
        "claude-3-5-haiku-20241022": 1729555200,  # 2024-10-22
        "claude-3-5-haiku-latest": 1729555200,  # 2024-10-22
        "claude-3-5-sonnet-20240620": 1718841600,  # 2024-06-20
        "claude-3-haiku-20240307": 1709769600,  # 2024-03-07
        "claude-3-opus-20240229": 1709164800,  # 2024-02-29
    }

    # Get supported Claude models from existing utility
    supported_models = get_supported_claude_models()

    # Create Anthropic-style model entries
    models = []
    for model_id in supported_models:
        models.append(
            {
                "type": "model",
                "id": model_id,
                "display_name": display_names.get(model_id, model_id),
                "created_at": timestamps.get(model_id, 1677610602),  # Default timestamp
            }
        )

    return models


def get_models_list() -> dict[str, Any]:
    """Get list of available Claude models.

    Returns:
        Dictionary with list of Claude models in Anthropic API format

    """
    anthropic_models = get_anthropic_models()

    return {
        "data": anthropic_models,
        "has_more": False,
        "object": "list",
    }


__all__ = [
    "get_anthropic_models",
    "get_models_list",
]
