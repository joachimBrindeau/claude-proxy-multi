"""Shared test data constants and builders for API tests.

This module provides centralized test data to reduce duplication across test files
and ensure consistency in test scenarios.
"""

from typing import Any


# Standard model names used across tests
CLAUDE_SONNET_MODEL = "claude-3-5-sonnet-20241022"
INVALID_MODEL_NAME = "invalid-model"

# Common request data structures
STANDARD_OPENAI_REQUEST: dict[str, Any] = {
    "model": CLAUDE_SONNET_MODEL,
    "messages": [{"role": "user", "content": "Hello, world!"}],
    "max_tokens": 100,
    "temperature": 0.7,
}

STANDARD_ANTHROPIC_REQUEST: dict[str, Any] = {
    "model": CLAUDE_SONNET_MODEL,
    "max_tokens": 100,
    "messages": [{"role": "user", "content": "Hello, Claude!"}],
}

OPENAI_REQUEST_WITH_SYSTEM: dict[str, Any] = {
    "model": CLAUDE_SONNET_MODEL,
    "messages": [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello!"},
    ],
    "max_tokens": 50,
}

ANTHROPIC_REQUEST_WITH_SYSTEM: dict[str, Any] = {
    "model": CLAUDE_SONNET_MODEL,
    "max_tokens": 100,
    "system": "You are a helpful assistant.",
    "messages": [{"role": "user", "content": "Hello!"}],
}

# Error test cases
INVALID_MODEL_OPENAI_REQUEST: dict[str, Any] = {
    "model": INVALID_MODEL_NAME,
    "messages": [{"role": "user", "content": "Hello"}],
    "max_tokens": 50,
}

INVALID_MODEL_ANTHROPIC_REQUEST: dict[str, Any] = {
    "model": INVALID_MODEL_NAME,
    "max_tokens": 100,
    "messages": [{"role": "user", "content": "Hello"}],
}

MISSING_MESSAGES_OPENAI_REQUEST: dict[str, Any] = {
    "model": CLAUDE_SONNET_MODEL,
    "max_tokens": 50,
}

EMPTY_MESSAGES_OPENAI_REQUEST: dict[str, Any] = {
    "model": CLAUDE_SONNET_MODEL,
    "messages": [],
    "max_tokens": 50,
}

MALFORMED_MESSAGE_OPENAI_REQUEST: dict[str, Any] = {
    "model": CLAUDE_SONNET_MODEL,
    "messages": [{"invalid_field": "user", "content": "Hello"}],
    "max_tokens": 50,
}

MISSING_MAX_TOKENS_ANTHROPIC_REQUEST: dict[str, Any] = {
    "model": CLAUDE_SONNET_MODEL,
    "messages": [{"role": "user", "content": "Hello"}],
}

INVALID_ROLE_ANTHROPIC_REQUEST: dict[str, Any] = {
    "model": CLAUDE_SONNET_MODEL,
    "max_tokens": 100,
    "messages": [{"role": "invalid", "content": "Hello"}],
}

# Streaming request variants
STREAMING_OPENAI_REQUEST: dict[str, Any] = {
    **STANDARD_OPENAI_REQUEST,
    "stream": True,
}

STREAMING_ANTHROPIC_REQUEST: dict[str, Any] = {
    **STANDARD_ANTHROPIC_REQUEST,
    "stream": True,
}

# Large request for testing body size limits
LARGE_CONTENT = "x" * 1000000  # 1MB of text
LARGE_REQUEST_ANTHROPIC: dict[str, Any] = {
    "model": CLAUDE_SONNET_MODEL,
    "max_tokens": 50,
    "messages": [{"role": "user", "content": LARGE_CONTENT}],
}

# Authentication test data
TEST_AUTH_TOKEN = "test-token-12345"
INVALID_AUTH_TOKEN = "invalid-token"

# Expected response field sets for validation
OPENAI_RESPONSE_FIELDS = {"id", "object", "created", "model", "choices", "usage"}
ANTHROPIC_RESPONSE_FIELDS = {
    "id",
    "type",
    "role",
    "content",
    "model",
    "stop_reason",
    "usage",
}


def create_openai_request(
    content: str = "Hello",
    model: str = CLAUDE_SONNET_MODEL,
    max_tokens: int = 50,
    **kwargs: Any,
) -> dict[str, Any]:
    """Create a customizable OpenAI request."""
    request = {
        "model": model,
        "messages": [{"role": "user", "content": content}],
        "max_tokens": max_tokens,
    }
    request.update(kwargs)
    return request


def create_anthropic_request(
    content: str = "Hello",
    model: str = CLAUDE_SONNET_MODEL,
    max_tokens: int = 50,
    **kwargs: Any,
) -> dict[str, Any]:
    """Create a customizable Anthropic request."""
    request = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": content}],
    }
    request.update(kwargs)
    return request
