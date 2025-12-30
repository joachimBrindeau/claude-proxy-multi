"""Adapter modules for API format conversion."""

from claude_code_proxy.adapters.base import APIAdapter

from .openai import OpenAIAdapter


__all__ = [
    "APIAdapter",
    "OpenAIAdapter",
]
