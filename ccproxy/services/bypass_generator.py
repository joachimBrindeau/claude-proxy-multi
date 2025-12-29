"""Bypass generator for mock API responses.

This module provides realistic mock responses for testing and development,
bypassing the actual upstream API when the X-CCProxy-Bypass-Upstream header is set.
"""

import asyncio
import random
import time
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING, Any

import orjson
import structlog
from fastapi.responses import StreamingResponse

from ccproxy.observability.access_logger import log_request_access
from ccproxy.observability.streaming_response import StreamingResponseWithLogging


if TYPE_CHECKING:
    from ccproxy.adapters.openai.adapter import OpenAIAdapter
    from ccproxy.observability import PrometheusMetrics
    from ccproxy.observability.context import RequestContext
    from ccproxy.testing import RealisticMockResponseGenerator

logger = structlog.get_logger(__name__)


class BypassGenerator:
    """Generates realistic mock API responses for bypass mode.

    Provides both standard and streaming response generation with
    realistic latency, token counts, and cost calculations.
    """

    def __init__(
        self,
        mock_generator: "RealisticMockResponseGenerator",
        openai_adapter: "OpenAIAdapter",
        metrics: "PrometheusMetrics",
    ) -> None:
        """Initialize the bypass generator.

        Args:
            mock_generator: Generator for realistic mock responses
            openai_adapter: Adapter for OpenAI format transformation
            metrics: Prometheus metrics collector
        """
        self.mock_generator = mock_generator
        self.openai_adapter = openai_adapter
        self.metrics = metrics

    async def generate_standard(
        self,
        model: str | None,
        is_openai_format: bool,
        ctx: "RequestContext",
        message_type: str = "short",
    ) -> tuple[int, dict[str, str], bytes]:
        """Generate realistic mock standard response.

        Args:
            model: Model name for the response
            is_openai_format: Whether to return OpenAI format
            ctx: Request context for metrics
            message_type: Type of response ("short", "medium", "long", "tool_use")

        Returns:
            Tuple of (status_code, headers, body)
        """
        # Check if we should simulate an error
        if self.mock_generator.should_simulate_error():
            error_response, status_code = self.mock_generator.generate_error_response(
                "openai" if is_openai_format else "anthropic"
            )
            response_body = orjson.dumps(error_response)
            return status_code, {"content-type": "application/json"}, response_body

        # Generate realistic content and token counts
        content, input_tokens, output_tokens = (
            self.mock_generator.generate_response_content(
                message_type, model or "claude-3-5-sonnet-20241022"
            )
        )
        cache_read_tokens, cache_write_tokens = (
            self.mock_generator.generate_cache_tokens()
        )

        # Simulate realistic latency
        latency_ms = random.randint(*self.mock_generator.config.base_latency_ms)
        await asyncio.sleep(latency_ms / 1000.0)

        # Always start with Anthropic format
        request_id = f"msg_test_{ctx.request_id}_{random.randint(1000, 9999)}"
        content_list: list[dict[str, Any]] = [{"type": "text", "text": content}]
        anthropic_response = {
            "id": request_id,
            "type": "message",
            "role": "assistant",
            "content": content_list,
            "model": model or "claude-3-5-sonnet-20241022",
            "stop_reason": "end_turn",
            "stop_sequence": None,
            "usage": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cache_creation_input_tokens": cache_write_tokens,
                "cache_read_input_tokens": cache_read_tokens,
            },
        }

        # Add tool use if appropriate
        if message_type == "tool_use":
            content_list.insert(
                0,
                {
                    "type": "tool_use",
                    "id": f"toolu_{random.randint(10000, 99999)}",
                    "name": "calculator",
                    "input": {"expression": "23 * 45"},
                },
            )

        if is_openai_format:
            # Transform to OpenAI format using existing adapter
            openai_response = self.openai_adapter.adapt_response(anthropic_response)
            response_body = orjson.dumps(openai_response)
        else:
            response_body = orjson.dumps(anthropic_response)

        headers = {
            "content-type": "application/json",
            "content-length": str(len(response_body)),
        }

        # Update context with realistic metrics
        ctx.add_metadata(
            status_code=200,
            tokens_input=input_tokens,
            tokens_output=output_tokens,
            cache_read_tokens=cache_read_tokens,
            cache_write_tokens=cache_write_tokens,
        )

        # Log comprehensive access log (includes Prometheus metrics)
        await log_request_access(
            context=ctx,
            status_code=200,
            method="POST",
            metrics=self.metrics,
        )

        return 200, headers, response_body

    async def generate_streaming(
        self,
        model: str | None,
        is_openai_format: bool,
        ctx: "RequestContext",
        message_type: str = "short",
    ) -> StreamingResponse:
        """Generate realistic mock streaming response.

        Args:
            model: Model name for the response
            is_openai_format: Whether to return OpenAI format
            ctx: Request context for metrics
            message_type: Type of response ("short", "medium", "long", "tool_use")

        Returns:
            StreamingResponse with mock data
        """
        # Generate content and tokens
        content, input_tokens, output_tokens = (
            self.mock_generator.generate_response_content(
                message_type, model or "claude-3-5-sonnet-20241022"
            )
        )
        cache_read_tokens, cache_write_tokens = (
            self.mock_generator.generate_cache_tokens()
        )

        async def realistic_mock_stream_generator() -> AsyncGenerator[bytes, None]:
            request_id = f"msg_test_{ctx.request_id}_{random.randint(1000, 9999)}"

            if is_openai_format:
                # Generate OpenAI-style streaming
                chunks = self._generate_realistic_openai_stream(
                    request_id,
                    model or "claude-3-5-sonnet-20241022",
                    content,
                    input_tokens,
                    output_tokens,
                )
            else:
                # Generate Anthropic-style streaming
                chunks = self.mock_generator.generate_realistic_anthropic_stream(
                    request_id,
                    model or "claude-3-5-sonnet-20241022",
                    content,
                    input_tokens,
                    output_tokens,
                    cache_read_tokens,
                    cache_write_tokens,
                )

            # Simulate realistic token generation rate
            tokens_per_second = self.mock_generator.config.token_generation_rate

            for i, chunk in enumerate(chunks):
                # Realistic delay based on token generation rate
                if i > 0:  # Don't delay the first chunk
                    # Estimate tokens in this chunk and calculate delay
                    chunk_tokens = len(str(chunk)) // 4  # Rough estimate
                    delay_seconds = chunk_tokens / tokens_per_second
                    # Add some randomness
                    delay_seconds *= random.uniform(0.5, 1.5)
                    await asyncio.sleep(max(0.01, delay_seconds))

                yield b"data: " + orjson.dumps(chunk) + b"\n\n"

            yield b"data: [DONE]\n\n"

        headers = {
            "content-type": "text/event-stream",
            "cache-control": "no-cache",
            "connection": "keep-alive",
        }

        # Update context with realistic metrics
        ctx.add_metadata(
            status_code=200,
            tokens_input=input_tokens,
            tokens_output=output_tokens,
            cache_read_tokens=cache_read_tokens,
            cache_write_tokens=cache_write_tokens,
        )

        return StreamingResponseWithLogging(
            content=realistic_mock_stream_generator(),
            request_context=ctx,
            metrics=self.metrics,
            headers=headers,
        )

    def _generate_realistic_openai_stream(
        self,
        request_id: str,
        model: str,
        content: str,
        input_tokens: int,
        output_tokens: int,
    ) -> list[dict[str, Any]]:
        """Generate realistic OpenAI streaming chunks by converting Anthropic format.

        Args:
            request_id: Unique request identifier
            model: Model name
            content: Response content
            input_tokens: Input token count
            output_tokens: Output token count

        Returns:
            List of OpenAI format streaming chunks
        """
        # Generate Anthropic chunks first
        anthropic_chunks = self.mock_generator.generate_realistic_anthropic_stream(
            request_id, model, content, input_tokens, output_tokens, 0, 0
        )

        # Convert to OpenAI format using the adapter
        openai_chunks = []
        for chunk in anthropic_chunks:
            # Use the OpenAI adapter to convert each chunk
            # This is a simplified conversion - in practice, you'd need a full streaming adapter
            if chunk.get("type") == "message_start":
                openai_chunks.append(
                    {
                        "id": f"chatcmpl-{request_id}",
                        "object": "chat.completion.chunk",
                        "created": int(time.time()),
                        "model": model,
                        "choices": [
                            {
                                "index": 0,
                                "delta": {"role": "assistant", "content": ""},
                                "finish_reason": None,
                            }
                        ],
                    }
                )
            elif chunk.get("type") == "content_block_delta":
                delta_text = chunk.get("delta", {}).get("text", "")
                openai_chunks.append(
                    {
                        "id": f"chatcmpl-{request_id}",
                        "object": "chat.completion.chunk",
                        "created": int(time.time()),
                        "model": model,
                        "choices": [
                            {
                                "index": 0,
                                "delta": {"content": delta_text},
                                "finish_reason": None,
                            }
                        ],
                    }
                )
            elif chunk.get("type") == "message_stop":
                openai_chunks.append(
                    {
                        "id": f"chatcmpl-{request_id}",
                        "object": "chat.completion.chunk",
                        "created": int(time.time()),
                        "model": model,
                        "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                    }
                )

        return openai_chunks
