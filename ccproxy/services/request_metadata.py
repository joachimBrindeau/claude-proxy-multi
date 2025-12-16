"""Pure utility functions for request metadata extraction.

This module provides stateless helper functions for extracting and transforming
request metadata. All functions are pure with no side effects.
"""

import json

import structlog


logger = structlog.get_logger(__name__)

# Sensitive headers that should be redacted in logs
SENSITIVE_HEADERS = frozenset({"authorization", "x-api-key", "cookie", "set-cookie"})


def extract_metadata(body: bytes | None) -> tuple[str | None, bool]:
    """Extract model and streaming flag from request body.

    Args:
        body: Request body bytes

    Returns:
        Tuple of (model, streaming)
    """
    if not body:
        return None, False

    try:
        body_data = json.loads(body.decode("utf-8"))
        model = body_data.get("model")
        streaming = body_data.get("stream", False)
        return model, streaming
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None, False


def extract_message_type(body: bytes | None) -> str:
    """Extract message type from request body for realistic response generation.

    Args:
        body: Request body bytes

    Returns:
        Message type: "tool_use", "long", "medium", or "short"
    """
    if not body:
        return "short"

    try:
        body_data = json.loads(body.decode("utf-8"))
        # Check if tools are present - indicates tool use
        if body_data.get("tools"):
            return "tool_use"

        # Check message content length to determine type
        messages = body_data.get("messages", [])
        if messages:
            content = str(messages[-1].get("content", ""))
            if len(content) > 200:
                return "long"
            elif len(content) < 50:
                return "short"
            else:
                return "medium"
    except (json.JSONDecodeError, UnicodeDecodeError):
        pass

    return "short"


def is_streaming_request(headers: dict[str, str]) -> bool:
    """Check if response should be streamed based on request headers.

    Args:
        headers: Request headers

    Returns:
        True if response should be streamed
    """
    # Check if client requested streaming
    accept_header = headers.get("accept", "").lower()
    should_stream = "text/event-stream" in accept_header or "stream" in accept_header
    logger.debug(
        "stream_check_completed",
        accept_header=accept_header,
        should_stream=should_stream,
    )
    return should_stream


def redact_sensitive_headers(headers: dict[str, str]) -> dict[str, str]:
    """Redact sensitive information from headers for safe logging.

    Args:
        headers: Original headers dictionary

    Returns:
        Headers dictionary with sensitive values redacted
    """
    return {
        k: "[REDACTED]" if k.lower() in SENSITIVE_HEADERS else v
        for k, v in headers.items()
    }
