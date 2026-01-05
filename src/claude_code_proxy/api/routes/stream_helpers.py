"""Helper utilities for SSE streaming in route handlers."""

from collections.abc import AsyncIterator
from typing import Any

import orjson
from fastapi import HTTPException, Request

from claude_code_proxy.core.request_context import RequestContext
from claude_code_proxy.models.messages import MessageCreateParams


def get_request_context(request: Request) -> RequestContext:
    """Extract request context from middleware state.

    Args:
        request: FastAPI request object

    Returns:
        Request context dictionary

    Raises:
        HTTPException: If request context is missing

    """
    request_context = getattr(request.state, "context", None)
    if request_context is None:
        raise HTTPException(
            status_code=500, detail="Internal server error: no request context"
        )
    return request_context  # type: ignore[no-any-return]


def extract_session_id_from_metadata(
    message_request: MessageCreateParams,
) -> str | None:
    """Extract session ID from message request metadata.

    Args:
        message_request: Anthropic message request

    Returns:
        Session ID if present in metadata, None otherwise

    """
    if not message_request.metadata:
        return None

    metadata_dict = message_request.metadata.model_dump()
    return metadata_dict.get("session_id")


async def create_openai_stream_generator(
    adapter: object, response: AsyncIterator[dict[str, Any]]
) -> AsyncIterator[bytes]:
    """Create OpenAI-formatted SSE stream generator.

    Args:
        adapter: OpenAI adapter instance with adapt_stream method
        response: Async iterator of response chunks

    Yields:
        SSE-formatted OpenAI chunks

    """
    async for openai_chunk in adapter.adapt_stream(response):  # type: ignore[attr-defined]
        yield b"data: " + orjson.dumps(openai_chunk) + b"\n\n"
    yield b"data: [DONE]\n\n"


async def create_anthropic_stream_generator(
    response: AsyncIterator[dict[str, Any]],
) -> AsyncIterator[bytes]:
    """Create Anthropic-formatted SSE stream generator.

    Args:
        response: Async iterator of response chunks

    Yields:
        SSE-formatted Anthropic chunks

    """
    async for chunk in response:
        if not chunk:
            continue

        # All chunks from Claude SDK should be dict format
        if isinstance(chunk, dict):
            event_type = chunk.get("type", "message_delta")
            yield f"event: {event_type}\n".encode()
            yield b"data: " + orjson.dumps(chunk) + b"\n\n"


def create_streaming_headers(
    actual_model: str | None = None,
    fallback_occurred: bool = False,
) -> dict[str, str]:
    """Create standard headers for SSE streaming.

    Args:
        actual_model: The actual model used (if different from requested)
        fallback_occurred: Whether model fallback occurred due to 403

    Returns:
        Dictionary of headers for SSE responses

    """
    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
    }

    # Add X-Actual-Model header when fallback occurred
    if fallback_occurred and actual_model:
        headers["X-Actual-Model"] = actual_model
        headers["X-Model-Fallback"] = "true"

    return headers
