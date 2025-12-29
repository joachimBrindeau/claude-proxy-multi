"""Streaming response handler for API proxy.

This module handles streaming request processing, including:
- Error handling before streaming starts
- SSE stream transformation between Anthropic and OpenAI formats
- Metrics collection during streaming
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING, Any

import httpx
import orjson
import structlog
from fastapi.responses import StreamingResponse
from httpx_sse import EventSource

from ccproxy.observability.streaming_response import StreamingResponseWithLogging
from ccproxy.services.request_metadata import redact_sensitive_headers
from ccproxy.utils.simple_request_logger import append_streaming_log


if TYPE_CHECKING:
    from ccproxy.adapters.openai.adapter import OpenAIAdapter
    from ccproxy.core.http_transformers import HTTPResponseTransformer
    from ccproxy.observability import PrometheusMetrics
    from ccproxy.observability.context import RequestContext
    from ccproxy.services.proxy_service import RequestData
    from ccproxy.services.verbose_logger import VerboseLogger

logger = structlog.get_logger(__name__)


class StreamingHandler:
    """Handles streaming request processing with format transformation.

    Encapsulates the streaming logic including error handling, metrics
    collection, and format transformation between Anthropic and OpenAI.
    """

    def __init__(
        self,
        response_transformer: HTTPResponseTransformer,
        openai_adapter: OpenAIAdapter,
        verbose_logger: VerboseLogger,
        metrics: PrometheusMetrics,
        proxy_url: str | None,
        ssl_context: Any,
        proxy_mode: str,
    ) -> None:
        """Initialize the streaming handler.

        Args:
            response_transformer: Transformer for response formats
            openai_adapter: Adapter for OpenAI format transformation
            verbose_logger: Logger for verbose output
            metrics: Prometheus metrics collector
            proxy_url: Optional proxy URL for requests
            ssl_context: SSL context for verification
            proxy_mode: Current proxy operation mode
        """
        self.response_transformer = response_transformer
        self.openai_adapter = openai_adapter
        self.verbose_logger = verbose_logger
        self.metrics = metrics
        self.proxy_url = proxy_url
        self.ssl_context = ssl_context
        self.proxy_mode = proxy_mode

    async def handle(
        self,
        request_data: RequestData,
        original_path: str,
        timeout: float,
        ctx: RequestContext,
    ) -> StreamingResponse | tuple[int, dict[str, str], bytes]:
        """Handle streaming request with transformation.

        Args:
            request_data: Transformed request data
            original_path: Original request path for context
            timeout: Request timeout
            ctx: Request context for observability

        Returns:
            StreamingResponse or error response tuple
        """
        # Log the outgoing request if verbose API logging is enabled
        await self.verbose_logger.log_api_request(request_data, ctx)

        # First, make the request and check for errors before streaming
        async with httpx.AsyncClient(
            timeout=timeout, proxy=self.proxy_url, verify=self.ssl_context
        ) as client:
            # Start the request to get headers
            response = await client.send(
                client.build_request(
                    method=request_data["method"],
                    url=request_data["url"],
                    headers=request_data["headers"],
                    content=request_data["body"],
                ),
                stream=True,
            )

            # Check for errors before starting to stream
            if response.status_code >= 400:
                return await self._handle_error_response(
                    response, request_data, original_path, ctx
                )

        # If no error, proceed with streaming
        return await self._create_streaming_response(
            request_data, original_path, timeout, ctx
        )

    async def _handle_error_response(
        self,
        response: httpx.Response,
        request_data: RequestData,
        original_path: str,
        ctx: RequestContext,
    ) -> tuple[int, dict[str, str], bytes]:
        """Handle error response before streaming starts.

        Args:
            response: Error response from upstream
            request_data: Original request data
            original_path: Original request path
            ctx: Request context

        Returns:
            Tuple of (status_code, headers, body)
        """
        error_content = await response.aread()

        # Log the full error response body
        await self.verbose_logger.log_api_response(
            response.status_code, dict(response.headers), error_content, ctx
        )

        logger.info(
            "streaming_error_received",
            status_code=response.status_code,
            error_detail=error_content.decode("utf-8", errors="replace"),
        )

        # Use transformer to handle error transformation (including OpenAI format)
        transformed_error_response = (
            await self.response_transformer.transform_proxy_response(
                response.status_code,
                dict(response.headers),
                error_content,
                original_path,
                self.proxy_mode,
            )
        )
        transformed_error_body = transformed_error_response["body"]

        # Update context with error status
        ctx.add_metadata(status_code=response.status_code)

        # Log access log for error
        from ccproxy.observability.access_logger import log_request_access

        await log_request_access(
            context=ctx,
            status_code=response.status_code,
            method=request_data["method"],
            metrics=self.metrics,
        )

        # Return error as regular response
        return (
            response.status_code,
            dict(response.headers),
            transformed_error_body,
        )

    async def _create_streaming_response(
        self,
        request_data: RequestData,
        original_path: str,
        timeout: float,
        ctx: RequestContext,
    ) -> StreamingResponse:
        """Create a streaming response with proper headers and generator.

        Args:
            request_data: Request data for upstream
            original_path: Original request path
            timeout: Request timeout
            ctx: Request context

        Returns:
            StreamingResponse with content generator
        """
        response_headers: dict[str, str] = {}
        response_status = 200

        # Make initial request to capture headers
        async with httpx.AsyncClient(
            timeout=timeout, proxy=self.proxy_url, verify=self.ssl_context
        ) as client:
            initial_response = await client.send(
                client.build_request(
                    method=request_data["method"],
                    url=request_data["url"],
                    headers=request_data["headers"],
                    content=request_data["body"],
                ),
                stream=True,
            )
            response_status = initial_response.status_code
            response_headers = dict(initial_response.headers)

            # Close the initial response since we'll make a new one in the generator
            await initial_response.aclose()

        # Create stream generator with all required context
        generator = self._create_stream_generator(
            request_data,
            original_path,
            timeout,
            ctx,
            response_status,
            response_headers,
        )

        # Build final headers
        final_headers = response_headers.copy()
        final_headers.pop("date", None)  # Remove upstream date header
        final_headers["Cache-Control"] = "no-cache"
        final_headers["Connection"] = "keep-alive"
        if "content-type" not in final_headers:
            final_headers["content-type"] = "text/event-stream"

        return StreamingResponseWithLogging(
            content=generator,
            request_context=ctx,
            metrics=self.metrics,
            status_code=response_status,
            headers=final_headers,
        )

    def _create_stream_generator(
        self,
        request_data: RequestData,
        original_path: str,
        timeout: float,
        ctx: RequestContext,
        response_status: int,
        response_headers: dict[str, str],
    ) -> AsyncGenerator[bytes, None]:
        """Create the async generator for streaming content.

        Args:
            request_data: Request data for upstream
            original_path: Original request path
            timeout: Request timeout
            ctx: Request context
            response_status: Initial response status
            response_headers: Initial response headers

        Returns:
            Async generator yielding stream chunks
        """
        # Initialize streaming metrics collector
        from ccproxy.utils.streaming_metrics import StreamingMetricsCollector

        metrics_collector = StreamingMetricsCollector(request_id=ctx.request_id)

        async def stream_generator() -> AsyncGenerator[bytes, None]:
            nonlocal response_status, response_headers

            try:
                logger.debug(
                    "stream_generator_start",
                    method=request_data["method"],
                    url=request_data["url"],
                    headers=request_data["headers"],
                )

                async with (
                    httpx.AsyncClient(
                        timeout=timeout, proxy=self.proxy_url, verify=self.ssl_context
                    ) as client,
                    client.stream(
                        method=request_data["method"],
                        url=request_data["url"],
                        headers=request_data["headers"],
                        content=request_data["body"],
                    ) as response,
                ):
                    logger.debug(
                        "stream_response_received",
                        status_code=response.status_code,
                        headers=dict(response.headers),
                    )

                    # Log initial stream response headers if verbose
                    if self.verbose_logger.verbose_api:
                        logger.info(
                            "verbose_api_stream_response_start",
                            status_code=response.status_code,
                            headers=redact_sensitive_headers(dict(response.headers)),
                        )

                    # Store response status and headers
                    response_status = response.status_code
                    response_headers = dict(response.headers)

                    # Log upstream response headers for streaming
                    if self.verbose_logger.verbose_api:
                        is_openai = self.response_transformer._is_openai_request(
                            original_path
                        )
                        await self.verbose_logger.log_stream_response_headers(
                            ctx=ctx,
                            status_code=response.status_code,
                            headers=dict(response.headers),
                            is_openai=is_openai,
                        )

                    # Transform streaming response based on format
                    is_openai = self.response_transformer._is_openai_request(
                        original_path
                    )
                    logger.debug(
                        "openai_format_check", is_openai=is_openai, path=original_path
                    )

                    if is_openai:
                        async for chunk in self._stream_openai_format(
                            response, original_path, ctx
                        ):
                            yield chunk
                    else:
                        async for chunk in self._stream_anthropic_format(
                            response, ctx, metrics_collector, response_status
                        ):
                            yield chunk

            except (
                httpx.HTTPError,
                httpx.TimeoutException,
                asyncio.CancelledError,
            ) as e:
                # HTTP errors, timeouts, or async cancellation during streaming
                logger.exception("streaming_error", error=str(e), exc_info=True)
                error_message = f'data: {{"error": "Streaming error: {str(e)}"}}\n\n'
                yield error_message.encode("utf-8")

        return stream_generator()

    async def _stream_openai_format(
        self,
        response: httpx.Response,
        original_path: str,
        ctx: RequestContext,
    ) -> AsyncGenerator[bytes, None]:
        """Stream content in OpenAI format.

        Args:
            response: Upstream response
            original_path: Original request path
            ctx: Request context

        Yields:
            Transformed OpenAI format chunks
        """
        logger.debug("sse_transform_start", path=original_path)

        request_id = ctx.request_id
        timestamp = ctx.get_log_timestamp_prefix()

        async for transformed_chunk in self._transform_anthropic_to_openai_stream(
            response, original_path
        ):
            # Log transformed streaming chunk
            await append_streaming_log(
                request_id=request_id,
                log_type="upstream_streaming",
                data=transformed_chunk,
                timestamp=timestamp,
            )

            logger.debug(
                "transformed_chunk_yielded",
                chunk_size=len(transformed_chunk),
            )
            yield transformed_chunk

    async def _stream_anthropic_format(
        self,
        response: httpx.Response,
        ctx: RequestContext,
        metrics_collector: Any,
        response_status: int,
    ) -> AsyncGenerator[bytes, None]:
        """Stream content in native Anthropic format.

        Args:
            response: Upstream response
            ctx: Request context
            metrics_collector: Collector for streaming metrics
            response_status: Response status code

        Yields:
            Raw Anthropic format chunks
        """
        logger.debug("anthropic_streaming_start")
        chunk_count = 0
        content_block_delta_count = 0

        verbose_streaming = self.verbose_logger.verbose_streaming
        request_id = ctx.request_id
        timestamp = ctx.get_log_timestamp_prefix()

        async for chunk in response.aiter_bytes():
            if chunk:
                chunk_count += 1

                # Log raw streaming chunk
                await append_streaming_log(
                    request_id=request_id,
                    log_type="upstream_streaming",
                    data=chunk,
                    timestamp=timestamp,
                )

                # Process chunk for metrics
                chunk_str = chunk.decode("utf-8", errors="replace")
                is_final = metrics_collector.process_chunk(chunk_str)

                # If this is the final chunk, update context with metrics
                if is_final:
                    final_metrics = metrics_collector.get_metrics()

                    ctx.add_metadata(
                        status_code=response_status,
                        tokens_input=final_metrics["tokens_input"],
                        tokens_output=final_metrics["tokens_output"],
                        cache_read_tokens=final_metrics["cache_read_tokens"],
                        cache_write_tokens=final_metrics["cache_write_tokens"],
                    )

                # Handle logging based on chunk type
                if "content_block_delta" in chunk_str and not verbose_streaming:
                    content_block_delta_count += 1
                    if content_block_delta_count == 1:
                        logger.debug("content_block_delta_start")
                    elif content_block_delta_count % 10 == 0:
                        logger.debug(
                            "content_block_delta_progress",
                            count=content_block_delta_count,
                        )
                elif verbose_streaming or "content_block_delta" not in chunk_str:
                    logger.debug(
                        "chunk_yielded",
                        chunk_number=chunk_count,
                        chunk_size=len(chunk),
                        chunk_preview=chunk[:100].decode("utf-8", errors="replace"),
                    )

                yield chunk

        # Final summary for content_block_delta events
        if content_block_delta_count > 0 and not verbose_streaming:
            logger.debug(
                "content_block_delta_completed",
                total_count=content_block_delta_count,
            )

    async def _transform_anthropic_to_openai_stream(
        self, response: httpx.Response, original_path: str
    ) -> AsyncGenerator[bytes, None]:
        """Transform Anthropic SSE stream to OpenAI SSE format.

        Uses httpx-sse EventSource for proper SSE parsing.

        Args:
            response: Streaming response from Anthropic
            original_path: Original request path for context

        Yields:
            Transformed OpenAI SSE format chunks
        """

        async def sse_to_dict_stream() -> AsyncGenerator[dict[str, object], None]:
            chunk_count = 0
            event_source = EventSource(response)
            async for sse in event_source.aiter_sse():
                if sse.data and sse.data != "[DONE]":
                    try:
                        chunk_data = orjson.loads(sse.data)
                        chunk_count += 1
                        logger.debug(
                            "proxy_anthropic_chunk_received",
                            chunk_count=chunk_count,
                            chunk_type=chunk_data.get("type"),
                            chunk=chunk_data,
                        )
                        yield chunk_data
                    except ValueError:
                        logger.warning("sse_parse_failed", data=sse.data)
                        continue

        # Transform using OpenAI adapter and format back to SSE
        async for openai_chunk in self.openai_adapter.adapt_stream(
            sse_to_dict_stream()
        ):
            sse_line = f"data: {orjson.dumps(openai_chunk).decode()}\n\n"
            yield sse_line.encode("utf-8")
