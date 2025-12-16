"""OpenAI Codex API routes."""

import json
import time
import uuid
from collections.abc import AsyncIterator

import httpx
import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from httpx_sse import EventSource, ServerSentEvent
from fastapi.responses import StreamingResponse
from starlette.responses import Response

from ccproxy.adapters.openai.models import (
    OpenAIChatCompletionRequest,
    OpenAIChatCompletionResponse,
)
from ccproxy.adapters.openai.response_adapter import ResponseAdapter
from ccproxy.api.dependencies import ProxyServiceDep
from ccproxy.auth.openai import OpenAITokenManager
from ccproxy.config.settings import Settings, get_settings
from ccproxy.core.errors import AuthenticationError, ProxyError
from ccproxy.observability.streaming_response import StreamingResponseWithLogging


logger = structlog.get_logger(__name__)

# Create router
router = APIRouter(prefix="/codex", tags=["codex"])


def get_token_manager() -> OpenAITokenManager:
    """Get OpenAI token manager dependency."""
    return OpenAITokenManager()


def resolve_session_id(
    path_session: str | None = None,
    header_session: str | None = None,
) -> str:
    """Resolve session ID with priority: path > header > generated."""
    return path_session or header_session or str(uuid.uuid4())


def build_openai_chunk(
    stream_id: str,
    created: int,
    *,
    content: str | None = None,
    role: str | None = None,
    finish_reason: str | None = None,
    model: str = "gpt-5",
    usage: dict[str, int] | None = None,
) -> bytes:
    """Build an OpenAI chat completion chunk in SSE format.

    Args:
        stream_id: The stream ID for this completion
        created: Unix timestamp when created
        content: Text content for delta (mutually exclusive with role)
        role: Role for initial chunk (mutually exclusive with content)
        finish_reason: "stop" for final chunk, None otherwise
        model: Model identifier
        usage: Optional token usage dict

    Returns:
        SSE-formatted chunk as bytes
    """
    delta: dict[str, str] = {}
    if role is not None:
        delta["role"] = role
    elif content is not None:
        delta["content"] = content
    # else: empty delta for final chunk

    chunk: dict = {
        "id": stream_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": model,
        "choices": [
            {
                "index": 0,
                "delta": delta,
                "finish_reason": finish_reason,
            }
        ],
    }

    if usage:
        chunk["usage"] = usage

    return f"data: {json.dumps(chunk)}\n\n".encode()


async def check_codex_enabled(settings: Settings = Depends(get_settings)) -> None:
    """Check if Codex is enabled."""
    if not settings.codex.enabled:
        raise HTTPException(
            status_code=503, detail="OpenAI Codex provider is not enabled"
        )


@router.post("/responses", response_model=None)
async def codex_responses(
    request: Request,
    proxy_service: ProxyServiceDep,
    settings: Settings = Depends(get_settings),
    token_manager: OpenAITokenManager = Depends(get_token_manager),
    _: None = Depends(check_codex_enabled),
) -> StreamingResponse | Response:
    """Create completion with auto-generated session_id.

    This endpoint creates a new completion request with an automatically
    generated session_id. Each request gets a unique session.
    """
    # Get session_id from header if provided
    header_session_id = request.headers.get("session_id")
    session_id = resolve_session_id(header_session=header_session_id)

    # Get and validate access token
    try:
        access_token = await token_manager.get_valid_token()
        if not access_token:
            raise HTTPException(
                status_code=401,
                detail="No valid OpenAI credentials found. Please authenticate first.",
            )
    except HTTPException:
        # Re-raise HTTPExceptions without chaining to avoid stack traces
        raise
    except Exception as e:
        logger.debug(
            "Failed to get OpenAI access token",
            error=str(e),
            error_type=type(e).__name__,
        )
        raise HTTPException(
            status_code=401, detail="Failed to retrieve valid credentials"
        ) from None

    try:
        # Handle the Codex request
        response = await proxy_service.handle_codex_request(
            method="POST",
            path="/responses",
            session_id=session_id,
            access_token=access_token,
            request=request,
            settings=settings,
        )
        return response
    except AuthenticationError as e:
        raise HTTPException(status_code=401, detail=str(e)) from None
    except ProxyError as e:
        raise HTTPException(status_code=502, detail=str(e)) from None
    except Exception as e:
        logger.error("Unexpected error in codex_responses", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error") from None


@router.post("/{session_id}/responses", response_model=None)
async def codex_responses_with_session(
    session_id: str,
    request: Request,
    proxy_service: ProxyServiceDep,
    settings: Settings = Depends(get_settings),
    token_manager: OpenAITokenManager = Depends(get_token_manager),
    _: None = Depends(check_codex_enabled),
) -> StreamingResponse | Response:
    """Create completion with specific session_id.

    This endpoint creates a completion request using the provided session_id
    from the URL path. This allows for session-specific conversations.
    """
    # Get and validate access token
    try:
        access_token = await token_manager.get_valid_token()
        if not access_token:
            raise HTTPException(
                status_code=401,
                detail="No valid OpenAI credentials found. Please authenticate first.",
            )
    except HTTPException:
        # Re-raise HTTPExceptions without chaining to avoid stack traces
        raise
    except Exception as e:
        logger.debug(
            "Failed to get OpenAI access token",
            error=str(e),
            error_type=type(e).__name__,
        )
        raise HTTPException(
            status_code=401, detail="Failed to retrieve valid credentials"
        ) from None

    try:
        # Handle the Codex request with specific session_id
        response = await proxy_service.handle_codex_request(
            method="POST",
            path=f"/{session_id}/responses",
            session_id=session_id,
            access_token=access_token,
            request=request,
            settings=settings,
        )
        return response
    except AuthenticationError as e:
        raise HTTPException(status_code=401, detail=str(e)) from None
    except ProxyError as e:
        raise HTTPException(status_code=502, detail=str(e)) from None
    except Exception as e:
        logger.error("Unexpected error in codex_responses_with_session", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error") from None


@router.post("/chat/completions", response_model=None)
async def codex_chat_completions(
    openai_request: OpenAIChatCompletionRequest,
    request: Request,
    proxy_service: ProxyServiceDep,
    settings: Settings = Depends(get_settings),
    token_manager: OpenAITokenManager = Depends(get_token_manager),
    _: None = Depends(check_codex_enabled),
) -> StreamingResponse | OpenAIChatCompletionResponse:
    """OpenAI-compatible chat completions endpoint for Codex.

    This endpoint accepts OpenAI chat/completions format and converts it
    to OpenAI Response API format before forwarding to the ChatGPT backend.
    """
    # Get session_id from header if provided, otherwise generate
    header_session_id = request.headers.get("session_id")
    session_id = resolve_session_id(header_session=header_session_id)

    # Get and validate access token
    try:
        access_token = await token_manager.get_valid_token()
        if not access_token:
            raise HTTPException(
                status_code=401,
                detail="No valid OpenAI credentials found. Please authenticate first.",
            )
    except HTTPException:
        # Re-raise HTTPExceptions without chaining to avoid stack traces
        raise
    except Exception as e:
        logger.debug(
            "Failed to get OpenAI access token",
            error=str(e),
            error_type=type(e).__name__,
        )
        raise HTTPException(
            status_code=401, detail="Failed to retrieve valid credentials"
        ) from None

    try:
        # Create adapter for format conversion
        adapter = ResponseAdapter()

        # Convert OpenAI Chat Completions format to Response API format
        response_request = adapter.chat_to_response_request(openai_request)

        # Convert the transformed request to bytes
        codex_body = response_request.model_dump_json().encode("utf-8")

        # Get request context from middleware
        request_context = getattr(request.state, "context", None)

        # Create a mock request object with the converted body
        class MockRequest:
            def __init__(self, original_request: Request, new_body: bytes) -> None:
                self.method = original_request.method
                self.url = original_request.url
                self.headers = dict(original_request.headers)
                self.headers["content-length"] = str(len(new_body))
                self.state = original_request.state
                self._body = new_body

            async def body(self) -> bytes:
                return self._body

        mock_request = MockRequest(request, codex_body)

        # For streaming requests, handle the transformation directly
        if openai_request.stream:
            # Make the request directly to get the raw streaming response
            from ccproxy.core.codex_transformers import CodexRequestTransformer

            # Transform the request
            transformer = CodexRequestTransformer()
            transformed_request = await transformer.transform_codex_request(
                method="POST",
                path="/responses",
                headers=dict(request.headers),
                body=codex_body,
                access_token=access_token,
                session_id=session_id,
                account_id="unknown",  # Will be extracted from token if needed
                codex_detection_data=getattr(
                    proxy_service.app_state, "codex_detection_data", None
                )
                if proxy_service.app_state
                else None,
                target_base_url=settings.codex.base_url,
            )

            # Convert Response API SSE stream to Chat Completions format
            response_headers = {}
            # Generate stream_id and timestamp outside the nested function to avoid closure issues
            stream_id = f"chatcmpl_{uuid.uuid4().hex[:29]}"
            created = int(time.time())

            async def stream_codex_response() -> AsyncIterator[bytes]:
                """Stream and convert Response API to Chat Completions format."""
                async with (
                    httpx.AsyncClient(timeout=240.0) as client,
                    client.stream(
                        method="POST",
                        url=transformed_request["url"],
                        headers=transformed_request["headers"],
                        content=transformed_request["body"],
                    ) as response,
                ):
                    # Check if we got a streaming response
                    content_type = response.headers.get("content-type", "")
                    transfer_encoding = response.headers.get("transfer-encoding", "")

                    # Capture response headers for forwarding
                    nonlocal response_headers
                    response_headers = dict(response.headers)

                    logger.debug(
                        "codex_chat_response_headers",
                        status_code=response.status_code,
                        content_type=content_type,
                        transfer_encoding=transfer_encoding,
                        headers=response_headers,
                        url=str(response.url),
                    )

                    # Check for error response first
                    if response.status_code >= 400:
                        # Handle error response - collect the response body
                        error_body = b""
                        async for chunk in response.aiter_bytes():
                            error_body += chunk

                        # Try to parse error message
                        error_message = "Request failed"
                        if error_body:
                            try:
                                error_data = json.loads(error_body.decode("utf-8"))
                                if "detail" in error_data:
                                    error_message = error_data["detail"]
                                elif "error" in error_data and isinstance(
                                    error_data["error"], dict
                                ):
                                    error_message = error_data["error"].get(
                                        "message", "Request failed"
                                    )
                            except json.JSONDecodeError:
                                pass

                        logger.warning(
                            "codex_chat_error_response",
                            status_code=response.status_code,
                            error_message=error_message,
                        )

                        # Return error in streaming format
                        error_response = {
                            "error": {
                                "message": error_message,
                                "type": "invalid_request_error",
                                "code": response.status_code,
                            }
                        }
                        yield f"data: {json.dumps(error_response)}\n\n".encode()
                        return

                    # Check if this is a streaming response
                    # The backend may return chunked transfer encoding without content-type
                    is_streaming = "text/event-stream" in content_type or (
                        transfer_encoding == "chunked" and not content_type
                    )

                    if is_streaming:
                        logger.debug(
                            "codex_stream_conversion_started",
                            session_id=session_id,
                            request_id=getattr(request.state, "request_id", "unknown"),
                        )

                        chunk_count = 0
                        total_bytes = 0

                        # Process SSE events using httpx-sse
                        event_count = 0
                        first_chunk_sent = False
                        thinking_block_active = False
                        try:
                            event_source = EventSource(response)
                            async for sse in event_source.aiter_sse():
                                event_count += 1
                                logger.debug(
                                    "codex_stream_event",
                                    event_number=event_count,
                                    data_preview=sse.data[:100] if sse.data else "(empty)",
                                )

                                # Skip [DONE] or empty data
                                if not sse.data or sse.data == "[DONE]":
                                    continue

                                try:
                                    event_data = json.loads(sse.data)
                                    event_type = event_data.get("type")

                                    # Send initial role message if this is the first chunk
                                    if not first_chunk_sent:
                                        yield build_openai_chunk(
                                            stream_id, created, role="assistant"
                                        )
                                        first_chunk_sent = True
                                        chunk_count += 1

                                        logger.debug(
                                            "codex_stream_initial_chunk_sent",
                                            event_type=event_type,
                                        )

                                    # Handle reasoning blocks based on official OpenAI Response API
                                    if event_type == "response.output_item.added":
                                        # Check if this is a reasoning block
                                        item = event_data.get("item", {})
                                        item_type = item.get("type")

                                        if (
                                            item_type == "reasoning"
                                            and not thinking_block_active
                                        ):
                                            # Only send opening tag if not already in a thinking block
                                            thinking_block_active = True

                                            logger.debug(
                                                "codex_reasoning_block_started",
                                                item_type=item_type,
                                                event_type=event_type,
                                            )

                                            # Send opening reasoning tag (no signature in official API)
                                            yield build_openai_chunk(
                                                stream_id, created, content="<reasoning>"
                                            )
                                            chunk_count += 1

                                    # Handle content part deltas - various content types from API
                                    elif (
                                        event_type == "response.content_part.delta"
                                    ):
                                        delta = event_data.get("delta", {})
                                        delta_type = delta.get("type")

                                        if (
                                            delta_type == "text"
                                            and not thinking_block_active
                                        ):
                                            # Regular text content
                                            text_content = delta.get("text", "")
                                            if text_content:
                                                yield build_openai_chunk(
                                                    stream_id, created, content=text_content
                                                )
                                                chunk_count += 1

                                        elif (
                                            delta_type == "reasoning"
                                            and thinking_block_active
                                        ):
                                            # Reasoning content within reasoning block
                                            reasoning_content = delta.get(
                                                "reasoning", ""
                                            )
                                            if reasoning_content:
                                                yield build_openai_chunk(
                                                    stream_id, created, content=reasoning_content
                                                )
                                                chunk_count += 1

                                    # Handle reasoning summary text - the actual reasoning content
                                    elif (
                                        event_type
                                        == "response.reasoning_summary_text.delta"
                                        and thinking_block_active
                                    ):
                                        # Extract reasoning text content from delta field
                                        reasoning_text = event_data.get("delta", "")

                                        if reasoning_text:
                                            chunk_count += 1
                                            yield build_openai_chunk(
                                                stream_id, created, content=reasoning_text
                                            )

                                    # Handle reasoning block completion - official API
                                    elif (
                                        event_type == "response.output_item.done"
                                        and thinking_block_active
                                    ):
                                        # Check if this is the end of a reasoning block
                                        item = event_data.get("item", {})
                                        item_type = item.get("type")

                                        if item_type == "reasoning":
                                            thinking_block_active = False

                                            # Send closing reasoning tag
                                            yield build_openai_chunk(
                                                stream_id, created, content="</reasoning>\n"
                                            )
                                            chunk_count += 1

                                            logger.debug(
                                                "codex_reasoning_block_ended",
                                                item_type=item_type,
                                                event_type=event_type,
                                            )

                                    # Convert Response API events to OpenAI format
                                    elif event_type == "response.output_text.delta":
                                        # Direct text delta event (only if not in thinking block)
                                        if not thinking_block_active:
                                            delta_content = event_data.get(
                                                "delta", ""
                                            )
                                            if delta_content:
                                                chunk_count += 1
                                                chunk_data = build_openai_chunk(
                                                    stream_id,
                                                    created,
                                                    content=delta_content,
                                                    model=event_data.get("model", "gpt-5"),
                                                )
                                                total_bytes += len(chunk_data)

                                                logger.debug(
                                                    "codex_stream_chunk_converted",
                                                    chunk_number=chunk_count,
                                                    chunk_size=len(chunk_data),
                                                    event_type=event_type,
                                                    content_length=len(delta_content),
                                                )

                                                yield chunk_data

                                    elif event_type == "response.output.delta":
                                        # Standard output delta with nested structure
                                        output = event_data.get("output", [])
                                        for output_item in output:
                                            if output_item.get("type") == "message":
                                                content_blocks = output_item.get(
                                                    "content", []
                                                )
                                                for block in content_blocks:
                                                    # Check if this is thinking content
                                                    if (
                                                        block.get("type")
                                                        in [
                                                            "thinking",
                                                            "reasoning",
                                                            "internal_monologue",
                                                        ]
                                                        and thinking_block_active
                                                    ):
                                                        thinking_content = (
                                                            block.get("text", "")
                                                        )
                                                        if thinking_content:
                                                            chunk_count += 1
                                                            yield build_openai_chunk(
                                                                stream_id,
                                                                created,
                                                                content=thinking_content,
                                                            )
                                                    elif (
                                                        block.get("type")
                                                        in [
                                                            "output_text",
                                                            "text",
                                                        ]
                                                        and not thinking_block_active
                                                    ):
                                                        delta_content = block.get(
                                                            "text", ""
                                                        )
                                                        if delta_content:
                                                            chunk_count += 1
                                                            chunk_data = build_openai_chunk(
                                                                stream_id,
                                                                created,
                                                                content=delta_content,
                                                                model=event_data.get(
                                                                    "model", "gpt-5"
                                                                ),
                                                            )
                                                            total_bytes += len(chunk_data)

                                                            logger.debug(
                                                                "codex_stream_chunk_converted",
                                                                chunk_number=chunk_count,
                                                                chunk_size=len(chunk_data),
                                                                event_type=event_type,
                                                                content_length=len(
                                                                    delta_content
                                                                ),
                                                            )

                                                            yield chunk_data

                                    # Handle additional official API event types
                                    elif (
                                        event_type
                                        == "response.function_call_arguments.delta"
                                    ):
                                        # Function call arguments streaming - official API
                                        if not thinking_block_active:
                                            arguments = event_data.get(
                                                "arguments", ""
                                            )
                                            if arguments:
                                                chunk_count += 1
                                                yield build_openai_chunk(
                                                    stream_id, created, content=arguments
                                                )

                                    elif (
                                        event_type
                                        == "response.audio_transcript.delta"
                                    ):
                                        # Audio transcript streaming - official API
                                        if not thinking_block_active:
                                            transcript = event_data.get(
                                                "transcript", ""
                                            )
                                            if transcript:
                                                chunk_count += 1
                                                yield build_openai_chunk(
                                                    stream_id,
                                                    created,
                                                    content=f"[Audio: {transcript}]",
                                                )

                                    elif (
                                        event_type
                                        == "response.tool_calls.function.name"
                                    ):
                                        # Tool function name - official API
                                        if not thinking_block_active:
                                            function_name = event_data.get(
                                                "name", ""
                                            )
                                            if function_name:
                                                chunk_count += 1
                                                yield build_openai_chunk(
                                                    stream_id,
                                                    created,
                                                    content=f"[Function: {function_name}]",
                                                )

                                    elif event_type == "response.completed":
                                        # Final chunk with usage info
                                        response_obj = event_data.get(
                                            "response", {}
                                        )
                                        usage = response_obj.get("usage")

                                        # Convert usage to OpenAI format if present
                                        openai_usage = None
                                        if usage:
                                            openai_usage = {
                                                "prompt_tokens": usage.get(
                                                    "input_tokens", 0
                                                ),
                                                "completion_tokens": usage.get(
                                                    "output_tokens", 0
                                                ),
                                                "total_tokens": usage.get(
                                                    "total_tokens", 0
                                                ),
                                            }

                                        yield build_openai_chunk(
                                            stream_id,
                                            created,
                                            finish_reason="stop",
                                            model=response_obj.get("model", "gpt-5"),
                                            usage=openai_usage,
                                        )

                                        logger.debug(
                                            "codex_stream_completed",
                                            total_chunks=chunk_count,
                                            total_bytes=total_bytes,
                                        )

                                except json.JSONDecodeError as e:
                                    logger.debug(
                                        "codex_sse_parse_failed",
                                        data_preview=sse.data[:100] if sse.data else "(empty)",
                                        error=str(e),
                                    )
                                    continue

                        except Exception as e:
                            logger.error(
                                "codex_stream_error",
                                error=str(e),
                                event_count=event_count,
                            )
                            raise

                        # Send final [DONE] message
                        logger.debug(
                            "codex_stream_sending_done",
                            total_chunks=chunk_count,
                            total_bytes=total_bytes,
                        )
                        yield b"data: [DONE]\n\n"
                    else:
                        # Backend didn't return streaming or returned unexpected format
                        # When using client.stream(), we need to collect the response differently
                        chunks = []
                        async for chunk in response.aiter_bytes():
                            chunks.append(chunk)

                        response_body = b"".join(chunks)

                        logger.debug(
                            "codex_chat_non_streaming_response",
                            body_length=len(response_body),
                            body_preview=response_body[:200].decode(
                                "utf-8", errors="replace"
                            )
                            if response_body
                            else "empty",
                        )

                        if response_body:
                            # Check if it's actually SSE data that we missed
                            body_str = response_body.decode("utf-8")
                            if body_str.startswith("event:") or body_str.startswith(
                                "data:"
                            ):
                                # It's SSE data, try to extract the final JSON
                                logger.warning(
                                    "Backend returned SSE data but content-type was not text/event-stream"
                                )
                                lines = body_str.strip().split("\n")
                                for line in reversed(lines):
                                    if line.startswith("data:") and not line.endswith(
                                        "[DONE]"
                                    ):
                                        try:
                                            json_str = line[5:].strip()
                                            response_data = json.loads(json_str)
                                            if "response" in response_data:
                                                response_data = response_data[
                                                    "response"
                                                ]
                                            # Convert to OpenAI format and yield as a single chunk
                                            openai_response = (
                                                adapter.response_to_chat_completion(
                                                    response_data
                                                )
                                            )
                                            yield f"data: {openai_response.model_dump_json()}\n\n".encode()
                                            yield b"data: [DONE]\n\n"
                                            return
                                        except json.JSONDecodeError:
                                            continue
                                # Couldn't parse SSE data - yield error as SSE event
                                error_response = {
                                    "error": {
                                        "message": "Failed to parse SSE response data",
                                        "type": "invalid_response_error",
                                        "code": 502,
                                    }
                                }
                                yield f"data: {json.dumps(error_response)}\n\n".encode()
                                yield b"data: [DONE]\n\n"
                                return
                            else:
                                # Try to parse as regular JSON
                                try:
                                    response_data = json.loads(body_str)
                                    # Convert to Chat Completions format and yield as single chunk
                                    openai_response = (
                                        adapter.response_to_chat_completion(
                                            response_data
                                        )
                                    )
                                    yield f"data: {openai_response.model_dump_json()}\n\n".encode()
                                    yield b"data: [DONE]\n\n"
                                    return
                                except json.JSONDecodeError as e:
                                    logger.error(
                                        "Failed to parse non-streaming response",
                                        error=str(e),
                                        body_preview=body_str[:500],
                                    )
                                    error_response = {
                                        "error": {
                                            "message": "Invalid JSON response from backend",
                                            "type": "invalid_response_error",
                                            "code": 502,
                                        }
                                    }
                                    yield f"data: {json.dumps(error_response)}\n\n".encode()
                                    yield b"data: [DONE]\n\n"
                                    return
                        else:
                            # Empty response - yield error
                            error_response = {
                                "error": {
                                    "message": "Backend returned empty response",
                                    "type": "empty_response_error",
                                    "code": 502,
                                }
                            }
                            yield f"data: {json.dumps(error_response)}\n\n".encode()
                            yield b"data: [DONE]\n\n"
                            return

            # Execute the generator first to capture headers
            generator_chunks = []
            async for chunk in stream_codex_response():
                generator_chunks.append(chunk)

            # Forward upstream headers but filter out incompatible ones for streaming
            streaming_headers = dict(response_headers)
            # Remove headers that conflict with streaming responses
            streaming_headers.pop("content-length", None)
            streaming_headers.pop("content-encoding", None)
            streaming_headers.pop("date", None)
            # Set streaming-specific headers
            streaming_headers.update(
                {
                    "content-type": "text/event-stream",
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                }
            )

            # Replay the collected chunks
            async def replay_stream() -> AsyncIterator[bytes]:
                for chunk in generator_chunks:
                    yield chunk

            # Return streaming response with proper headers - handle missing request_context
            from ccproxy.observability.context import RequestContext

            # Create a minimal request context if none exists
            if request_context is None:
                request_context = RequestContext(
                    request_id=str(uuid.uuid4()),
                    start_time=time.perf_counter(),
                    logger=logger,
                )

            return StreamingResponseWithLogging(
                content=replay_stream(),
                request_context=request_context,
                metrics=getattr(proxy_service, "metrics", None),
                status_code=200,
                media_type="text/event-stream",
                headers=streaming_headers,
            )
        else:
            # Handle non-streaming request using the proxy service
            # Cast MockRequest to Request to satisfy type checker
            mock_request_typed: Request = mock_request  # type: ignore[assignment]
            response = await proxy_service.handle_codex_request(
                method="POST",
                path="/responses",
                session_id=session_id,
                access_token=access_token,
                request=mock_request_typed,
                settings=settings,
            )

            # Check if this is a streaming response (shouldn't happen for non-streaming requests)
            is_streaming_response = isinstance(response, StreamingResponse)

            if is_streaming_response and not openai_request.stream:
                # User requested non-streaming but backend returned streaming
                # Consume the stream and convert to non-streaming response
                accumulated_content = ""
                final_response = None

                error_response = None
                accumulated_chunks = ""

                async for chunk in response.body_iterator:  # type: ignore
                    chunk_str = chunk.decode("utf-8")
                    accumulated_chunks += chunk_str

                    # The Response API sends SSE events, but errors might be plain JSON
                    lines = chunk_str.strip().split("\n")
                    for line in lines:
                        if line.startswith("data:") and "[DONE]" not in line:
                            data_str = line[5:].strip()
                            try:
                                event_data = json.loads(data_str)
                                # Look for the completed response
                                if event_data.get("type") == "response.completed":
                                    final_response = event_data
                                # Also check if this is a direct error response (not SSE format)
                                elif (
                                    "detail" in event_data and "type" not in event_data
                                ):
                                    error_response = event_data
                            except json.JSONDecodeError:
                                continue

                # If we didn't find SSE events, try parsing the entire accumulated content as JSON
                if (
                    not final_response
                    and not error_response
                    and accumulated_chunks.strip()
                ):
                    try:
                        # Try to parse the entire content as JSON (for non-SSE error responses)
                        json_response = json.loads(accumulated_chunks.strip())
                        if (
                            "detail" in json_response
                            or "error" in json_response
                            or "message" in json_response
                        ):
                            error_response = json_response
                        else:
                            # Might be a valid response without SSE formatting
                            final_response = {"response": json_response}
                    except json.JSONDecodeError:
                        # Not valid JSON either
                        pass

                if final_response:
                    # Convert to Chat Completions format
                    return adapter.response_to_chat_completion(final_response)
                elif error_response:
                    # Handle error response
                    error_message = "Request failed"
                    if "detail" in error_response:
                        error_message = error_response["detail"]
                    elif "error" in error_response:
                        if isinstance(error_response["error"], dict):
                            error_message = error_response["error"].get(
                                "message", "Request failed"
                            )
                        else:
                            error_message = str(error_response["error"])
                    elif "message" in error_response:
                        error_message = error_response["message"]

                    # Log the error for debugging
                    logger.error(
                        "codex_streaming_error_response",
                        error_data=error_response,
                        error_message=error_message,
                    )

                    raise HTTPException(status_code=400, detail=error_message)
                else:
                    raise HTTPException(
                        status_code=502, detail="Failed to parse streaming response"
                    )
            else:
                # Non-streaming response - parse and convert
                if isinstance(response, Response):
                    # Check if this is an error response
                    if response.status_code >= 400:
                        # Return the error response as-is
                        error_body = response.body
                        if error_body:
                            try:
                                # Handle bytes/memoryview union
                                error_body_bytes = (
                                    bytes(error_body)
                                    if isinstance(error_body, memoryview)
                                    else error_body
                                )
                                error_data = json.loads(
                                    error_body_bytes.decode("utf-8")
                                )
                                # Log the actual error from backend
                                logger.error(
                                    "codex_backend_error",
                                    status_code=response.status_code,
                                    error_data=error_data,
                                )
                                # Pass through the error from backend
                                # Handle different error formats from backend
                                error_message = "Request failed"
                                if "detail" in error_data:
                                    error_message = error_data["detail"]
                                elif "error" in error_data:
                                    if isinstance(error_data["error"], dict):
                                        error_message = error_data["error"].get(
                                            "message", "Request failed"
                                        )
                                    else:
                                        error_message = str(error_data["error"])
                                elif "message" in error_data:
                                    error_message = error_data["message"]

                                raise HTTPException(
                                    status_code=response.status_code,
                                    detail=error_message,
                                )
                            except (json.JSONDecodeError, UnicodeDecodeError):
                                # Handle bytes/memoryview union for logging
                                error_body_bytes = (
                                    bytes(error_body)
                                    if isinstance(error_body, memoryview)
                                    else error_body
                                )
                                logger.error(
                                    "codex_backend_error_parse_failed",
                                    status_code=response.status_code,
                                    body=error_body_bytes[:500].decode(
                                        "utf-8", errors="replace"
                                    ),
                                )
                                pass
                        raise HTTPException(
                            status_code=response.status_code, detail="Request failed"
                        )

                    # Read the response body for successful responses
                    response_body = response.body
                    if response_body:
                        try:
                            # Handle bytes/memoryview union
                            response_body_bytes = (
                                bytes(response_body)
                                if isinstance(response_body, memoryview)
                                else response_body
                            )
                            response_data = json.loads(
                                response_body_bytes.decode("utf-8")
                            )
                            # Convert Response API format to Chat Completions format
                            return adapter.response_to_chat_completion(response_data)
                        except (json.JSONDecodeError, UnicodeDecodeError) as e:
                            logger.error("Failed to parse Codex response", error=str(e))
                            raise HTTPException(
                                status_code=502,
                                detail="Invalid response from Codex API",
                            ) from e

                # If we can't convert, return error
                raise HTTPException(
                    status_code=502, detail="Unable to process Codex response"
                )

    except HTTPException:
        raise
    except AuthenticationError as e:
        raise HTTPException(status_code=401, detail=str(e)) from None
    except ProxyError as e:
        raise HTTPException(status_code=502, detail=str(e)) from None
    except Exception as e:
        logger.error("Unexpected error in codex_chat_completions", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error") from None
