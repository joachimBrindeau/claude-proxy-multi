"""Claude SDK endpoints for CCProxy API Server."""

import asyncio
from collections.abc import AsyncIterator

import orjson
import structlog
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import ValidationError as PydanticValidationError

from claude_code_proxy.adapters.openai.adapter import (
    OpenAIAdapter,
    OpenAIChatCompletionRequest,
    OpenAIChatCompletionResponse,
)
from claude_code_proxy.api.dependencies import ClaudeServiceDep
from claude_code_proxy.api.routes.stream_helpers import (
    create_anthropic_stream_generator,
    create_streaming_headers,
    extract_session_id_from_metadata,
    get_request_context,
)
from claude_code_proxy.exceptions import CCProxyError
from claude_code_proxy.models.messages import MessageCreateParams, MessageResponse


# Create the router for Claude SDK endpoints
router = APIRouter(tags=["claude-sdk"])

logger = structlog.get_logger(__name__)


@router.post("/v1/chat/completions", response_model=None)
async def create_openai_chat_completion(
    openai_request: OpenAIChatCompletionRequest,
    claude_service: ClaudeServiceDep,
    request: Request,
) -> StreamingResponse | OpenAIChatCompletionResponse:
    """Create a chat completion using Claude SDK with OpenAI-compatible format.

    This endpoint handles OpenAI API format requests and converts them
    to Anthropic format before using the Claude SDK directly.
    """
    try:
        # Create adapter instance
        adapter = OpenAIAdapter()

        # Convert entire OpenAI request to Anthropic format using adapter
        anthropic_request = adapter.adapt_request(openai_request.model_dump())

        # Extract stream parameter
        stream = openai_request.stream or False

        # Get request context from middleware
        request_context = getattr(request.state, "context", None)

        if request_context is None:
            raise HTTPException(
                status_code=500, detail="Internal server error: no request context"
            )

        # Call Claude SDK service with adapted request
        response = await claude_service.create_completion(
            messages=anthropic_request["messages"],
            model=anthropic_request["model"],
            temperature=anthropic_request.get("temperature"),
            max_tokens=anthropic_request.get("max_tokens"),
            stream=stream,
            user_id=getattr(openai_request, "user", None),
            request_context=request_context,
        )

        if stream:
            # Handle streaming response
            async def openai_stream_generator() -> AsyncIterator[bytes]:
                # Use adapt_stream for streaming responses
                async for openai_chunk in adapter.adapt_stream(response):  # type: ignore[arg-type]
                    yield b"data: " + orjson.dumps(openai_chunk) + b"\n\n"
                # Send final chunk
                yield b"data: [DONE]\n\n"

            return StreamingResponse(
                content=openai_stream_generator(),
                status_code=200,
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                },
            )
        else:
            # Convert non-streaming response to OpenAI format using adapter
            # Convert MessageResponse model to dict for adapter
            # In non-streaming mode, response should always be MessageResponse
            assert isinstance(response, MessageResponse), (
                "Non-streaming response must be MessageResponse"
            )
            response_dict = response.model_dump()
            openai_response = adapter.adapt_response(response_dict)
            return OpenAIChatCompletionResponse.model_validate(openai_response)

    except (HTTPException, CCProxyError):
        # Re-raise HTTP and proxy errors to be handled by error middleware
        raise
    except asyncio.CancelledError:
        # Streaming was cancelled by client disconnect
        raise
    except PydanticValidationError as e:
        # Request/response validation failed
        raise HTTPException(
            status_code=400, detail=f"Validation error: {str(e)}"
        ) from e
    except (KeyError, TypeError, ValueError) as e:
        # Data transformation or format errors during request/response processing
        raise HTTPException(
            status_code=500, detail=f"Internal server error: {str(e)}"
        ) from e


@router.post(
    "/{session_id}/v1/chat/completions",
    response_model=None,
)
async def create_openai_chat_completion_with_session(
    session_id: str,
    openai_request: OpenAIChatCompletionRequest,
    claude_service: ClaudeServiceDep,
    request: Request,
) -> StreamingResponse | OpenAIChatCompletionResponse:
    """Create a chat completion using Claude SDK with OpenAI-compatible format and session ID.

    This endpoint handles OpenAI API format requests with session ID and converts them
    to Anthropic format before using the Claude SDK directly.
    """
    try:
        # Create adapter instance
        adapter = OpenAIAdapter()

        # Convert entire OpenAI request to Anthropic format using adapter
        anthropic_request = adapter.adapt_request(openai_request.model_dump())

        # Extract stream parameter
        stream = openai_request.stream or False

        # Get request context from middleware
        request_context = getattr(request.state, "context", None)

        if request_context is None:
            raise HTTPException(
                status_code=500, detail="Internal server error: no request context"
            )

        # Call Claude SDK service with adapted request and session_id
        response = await claude_service.create_completion(
            messages=anthropic_request["messages"],
            model=anthropic_request["model"],
            temperature=anthropic_request.get("temperature"),
            max_tokens=anthropic_request.get("max_tokens"),
            stream=stream,
            user_id=getattr(openai_request, "user", None),
            session_id=session_id,
            request_context=request_context,
        )

        if stream:
            # Handle streaming response
            async def openai_stream_generator() -> AsyncIterator[bytes]:
                # Use adapt_stream for streaming responses
                async for openai_chunk in adapter.adapt_stream(response):  # type: ignore[arg-type]
                    yield b"data: " + orjson.dumps(openai_chunk) + b"\n\n"
                # Send final chunk
                yield b"data: [DONE]\n\n"

            return StreamingResponse(
                content=openai_stream_generator(),
                status_code=200,
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                },
            )
        else:
            # Convert non-streaming response to OpenAI format using adapter
            # Convert MessageResponse model to dict for adapter
            # In non-streaming mode, response should always be MessageResponse
            assert isinstance(response, MessageResponse), (
                "Non-streaming response must be MessageResponse"
            )
            response_dict = response.model_dump()
            openai_response = adapter.adapt_response(response_dict)
            return OpenAIChatCompletionResponse.model_validate(openai_response)

    except (HTTPException, CCProxyError):
        # Re-raise HTTP and proxy errors to be handled by error middleware
        raise
    except asyncio.CancelledError:
        # Streaming was cancelled by client disconnect
        raise
    except PydanticValidationError as e:
        # Request/response validation failed
        raise HTTPException(
            status_code=400, detail=f"Validation error: {str(e)}"
        ) from e
    except (KeyError, TypeError, ValueError) as e:
        # Data transformation or format errors during request/response processing
        raise HTTPException(
            status_code=500, detail=f"Internal server error: {str(e)}"
        ) from e


@router.post(
    "/{session_id}/v1/messages",
    response_model=None,
)
async def create_anthropic_message_with_session(
    session_id: str,
    message_request: MessageCreateParams,
    claude_service: ClaudeServiceDep,
    request: Request,
) -> StreamingResponse | MessageResponse:
    """Create a message using Claude SDK with Anthropic format and session ID.

    This endpoint handles Anthropic API format requests with session ID directly
    using the Claude SDK without any format conversion.
    """
    try:
        # Extract parameters from Anthropic request
        messages = [msg.model_dump() for msg in message_request.messages]
        model = message_request.model
        temperature = message_request.temperature
        max_tokens = message_request.max_tokens
        stream = message_request.stream or False

        # Get request context from middleware
        request_context = getattr(request.state, "context", None)
        if request_context is None:
            raise HTTPException(
                status_code=500, detail="Internal server error: no request context"
            )

        # Call Claude SDK service directly with Anthropic format and session_id
        response = await claude_service.create_completion(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=stream,
            user_id=getattr(message_request, "user_id", None),
            session_id=session_id,
            request_context=request_context,
        )

        if stream:
            # Handle streaming response
            async def anthropic_stream_generator() -> AsyncIterator[bytes]:
                async for chunk in response:  # type: ignore[union-attr]
                    if chunk:
                        # All chunks from Claude SDK streaming should be dict format
                        # and need proper SSE event formatting
                        if isinstance(chunk, dict):
                            # Determine event type from chunk type
                            event_type = chunk.get("type", "message_delta")
                            yield f"event: {event_type}\n".encode()
                            yield b"data: " + orjson.dumps(chunk) + b"\n\n"
                        else:
                            # Fallback for unexpected format
                            yield b"data: " + orjson.dumps(chunk) + b"\n\n"
                # No final [DONE] chunk for Anthropic format

            return StreamingResponse(
                content=anthropic_stream_generator(),
                status_code=200,
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                },
            )
        else:
            # Return Anthropic format response directly
            return MessageResponse.model_validate(response)

    except (HTTPException, CCProxyError):
        # Re-raise HTTP and proxy errors to be handled by error middleware
        raise
    except asyncio.CancelledError:
        # Streaming was cancelled by client disconnect
        raise
    except PydanticValidationError as e:
        # Request/response validation failed
        raise HTTPException(
            status_code=400, detail=f"Validation error: {str(e)}"
        ) from e
    except (KeyError, TypeError, ValueError) as e:
        # Data transformation or format errors during request/response processing
        raise HTTPException(
            status_code=500, detail=f"Internal server error: {str(e)}"
        ) from e


@router.post("/v1/messages", response_model=None)
async def create_anthropic_message(
    message_request: MessageCreateParams,
    claude_service: ClaudeServiceDep,
    request: Request,
) -> StreamingResponse | MessageResponse:
    """Create a message using Claude SDK with Anthropic format.

    This endpoint handles Anthropic API format requests directly
    using the Claude SDK without any format conversion.
    """
    try:
        messages = [msg.model_dump() for msg in message_request.messages]
        stream = message_request.stream or False
        request_context = get_request_context(request)
        session_id = extract_session_id_from_metadata(message_request)

        response = await claude_service.create_completion(
            messages=messages,
            model=message_request.model,
            temperature=message_request.temperature,
            max_tokens=message_request.max_tokens,
            stream=stream,
            user_id=getattr(message_request, "user_id", None),
            session_id=session_id,
            request_context=request_context,
        )

        if stream:
            return StreamingResponse(
                content=create_anthropic_stream_generator(response),  # type: ignore[arg-type]
                status_code=200,
                media_type="text/event-stream",
                headers=create_streaming_headers(),
            )

        return MessageResponse.model_validate(response)

    except (HTTPException, CCProxyError):
        raise
    except asyncio.CancelledError:
        raise
    except PydanticValidationError as e:
        raise HTTPException(
            status_code=400, detail=f"Validation error: {str(e)}"
        ) from e
    except (KeyError, TypeError, ValueError) as e:
        raise HTTPException(
            status_code=500, detail=f"Internal server error: {str(e)}"
        ) from e
