"""OpenAI streaming response formatting.

This module provides Server-Sent Events (SSE) formatting for OpenAI-compatible
streaming responses.
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from typing import Any, Literal

import orjson
import structlog

from .models import (
    generate_openai_response_id,
)


logger = structlog.get_logger(__name__)


class OpenAISSEFormatter:
    """Formats streaming responses to match OpenAI's SSE format."""

    @staticmethod
    def format_data_event(data: dict[str, Any]) -> str:
        """Format a data event for OpenAI-compatible Server-Sent Events.

        Args:
            data: Event data dictionary

        Returns:
            Formatted SSE string

        """
        json_data = orjson.dumps(data).decode()
        return f"data: {json_data}\n\n"

    @staticmethod
    def format_first_chunk(
        message_id: str, model: str, created: int, role: str = "assistant"
    ) -> str:
        """Format the first chunk with role and basic metadata.

        Args:
            message_id: Unique identifier for the completion
            model: Model name being used
            created: Unix timestamp when the completion was created
            role: Role of the assistant

        Returns:
            Formatted SSE string

        """
        data = {
            "id": message_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "delta": {"role": role},
                    "logprobs": None,
                    "finish_reason": None,
                }
            ],
        }
        return OpenAISSEFormatter.format_data_event(data)

    @staticmethod
    def format_content_chunk(
        message_id: str, model: str, created: int, content: str, choice_index: int = 0
    ) -> str:
        """Format a content chunk with text delta.

        Args:
            message_id: Unique identifier for the completion
            model: Model name being used
            created: Unix timestamp when the completion was created
            content: Text content to include in the delta
            choice_index: Index of the choice (usually 0)

        Returns:
            Formatted SSE string

        """
        data = {
            "id": message_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "choices": [
                {
                    "index": choice_index,
                    "delta": {"content": content},
                    "logprobs": None,
                    "finish_reason": None,
                }
            ],
        }
        return OpenAISSEFormatter.format_data_event(data)

    @staticmethod
    def format_tool_call_chunk(
        message_id: str,
        model: str,
        created: int,
        tool_call_id: str,
        function_name: str | None = None,
        function_arguments: str | None = None,
        tool_call_index: int = 0,
        choice_index: int = 0,
    ) -> str:
        """Format a tool call chunk.

        Args:
            message_id: Unique identifier for the completion
            model: Model name being used
            created: Unix timestamp when the completion was created
            tool_call_id: ID of the tool call
            function_name: Name of the function being called
            function_arguments: Arguments for the function
            tool_call_index: Index of the tool call
            choice_index: Index of the choice (usually 0)

        Returns:
            Formatted SSE string

        """
        tool_call: dict[str, Any] = {
            "index": tool_call_index,
            "id": tool_call_id,
            "type": "function",
            "function": {},
        }

        if function_name is not None:
            tool_call["function"]["name"] = function_name

        if function_arguments is not None:
            tool_call["function"]["arguments"] = function_arguments

        data = {
            "id": message_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "choices": [
                {
                    "index": choice_index,
                    "delta": {"tool_calls": [tool_call]},
                    "logprobs": None,
                    "finish_reason": None,
                }
            ],
        }
        return OpenAISSEFormatter.format_data_event(data)

    @staticmethod
    def format_final_chunk(
        message_id: str,
        model: str,
        created: int,
        finish_reason: str = "stop",
        choice_index: int = 0,
        usage: dict[str, int] | None = None,
    ) -> str:
        """Format the final chunk with finish_reason.

        Args:
            message_id: Unique identifier for the completion
            model: Model name being used
            created: Unix timestamp when the completion was created
            finish_reason: Reason for completion (stop, length, tool_calls, etc.)
            choice_index: Index of the choice (usually 0)
            usage: Optional usage information to include

        Returns:
            Formatted SSE string

        """
        data = {
            "id": message_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "choices": [
                {
                    "index": choice_index,
                    "delta": {},
                    "logprobs": None,
                    "finish_reason": finish_reason,
                }
            ],
        }

        # Add usage if provided
        if usage:
            data["usage"] = usage

        return OpenAISSEFormatter.format_data_event(data)

    @staticmethod
    def format_error_chunk(
        message_id: str, model: str, created: int, error_type: str, error_message: str
    ) -> str:
        """Format an error chunk.

        Args:
            message_id: Unique identifier for the completion
            model: Model name being used
            created: Unix timestamp when the completion was created
            error_type: Type of error
            error_message: Error message

        Returns:
            Formatted SSE string

        """
        data = {
            "id": message_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "choices": [
                {"index": 0, "delta": {}, "logprobs": None, "finish_reason": "error"}
            ],
            "error": {"type": error_type, "message": error_message},
        }
        return OpenAISSEFormatter.format_data_event(data)

    @staticmethod
    def format_done() -> str:
        """Format the final DONE event.

        Returns:
            Formatted SSE termination string

        """
        return "data: [DONE]\n\n"


class OpenAIStreamProcessor:
    """Processes Anthropic/Claude streaming responses into OpenAI format."""

    def __init__(
        self,
        message_id: str | None = None,
        model: str = "claude-3-5-sonnet-20241022",
        created: int | None = None,
        enable_usage: bool = True,
        enable_tool_calls: bool = True,
        output_format: Literal["sse", "dict"] = "sse",
    ):
        """Initialize the stream processor.

        Args:
            message_id: Response ID, generated if not provided
            model: Model name for responses
            created: Creation timestamp, current time if not provided
            enable_usage: Whether to include usage information
            enable_tool_calls: Whether to process tool calls
            output_format: Output format - "sse" for Server-Sent Events strings, "dict" for dict objects

        """
        self.message_id = message_id or generate_openai_response_id()
        self.model = model
        self.created = created or int(time.time())
        self.enable_usage = enable_usage
        self.enable_tool_calls = enable_tool_calls
        self.output_format = output_format
        self.formatter = OpenAISSEFormatter()

        # State tracking
        self.role_sent = False
        self.accumulated_content = ""
        self.tool_calls: dict[str, dict[str, Any]] = {}
        self.usage_info: dict[str, int] | None = None
        # Thinking block tracking
        self.current_thinking_text = ""
        self.current_thinking_signature: str | None = None
        self.thinking_block_active = False

    async def process_stream(
        self, claude_stream: AsyncIterator[dict[str, Any]]
    ) -> AsyncIterator[str | dict[str, Any]]:
        """Process a Claude/Anthropic stream into OpenAI format.

        Args:
            claude_stream: Async iterator of Claude response chunks

        Yields:
            OpenAI-formatted SSE strings or dict objects based on output_format

        """
        try:
            chunk_count = 0
            processed_count = 0
            async for chunk in claude_stream:
                chunk_count += 1
                logger.debug(
                    "openai_stream_chunk_received",
                    chunk_count=chunk_count,
                    chunk_type=chunk.get("type"),
                    chunk=chunk,
                )
                async for sse_chunk in self._process_chunk(chunk):
                    processed_count += 1
                    logger.debug(
                        "openai_stream_chunk_processed",
                        processed_count=processed_count,
                        sse_chunk=sse_chunk,
                    )
                    yield sse_chunk

            logger.debug(
                "openai_stream_complete",
                total_chunks=chunk_count,
                processed_chunks=processed_count,
                usage_info=self.usage_info,
            )

            # Send final chunk
            if self.usage_info and self.enable_usage:
                yield self._format_chunk_output(
                    finish_reason="stop",
                    usage=self.usage_info,
                )
            else:
                yield self._format_chunk_output(finish_reason="stop")

            # Send DONE event (only for SSE format)
            if self.output_format == "sse":
                yield self.formatter.format_done()

        except orjson.JSONDecodeError as e:
            # JSON parsing errors during stream processing
            if self.output_format == "sse":
                yield self.formatter.format_error_chunk(
                    self.message_id, self.model, self.created, "json_error", str(e)
                )
                yield self.formatter.format_done()
            else:
                # Dict format error
                yield self._create_chunk_dict(finish_reason="error")

    def _extract_chunk_data(
        self, chunk: dict[str, Any]
    ) -> tuple[dict[str, Any], str | None]:
        """Extract chunk data and type from various formats.

        Handles both Claude SDK and standard Anthropic API formats:
        - Claude SDK format: {"event": "...", "data": {"type": "..."}}
        - Anthropic API format: {"type": "...", ...}

        Args:
            chunk: Raw chunk from the stream

        Returns:
            Tuple of (chunk_data, chunk_type)

        """
        event_type = chunk.get("event")
        if event_type:
            chunk_data = chunk.get("data", {})
            chunk_type = chunk_data.get("type")
        else:
            chunk_data = chunk
            chunk_type = chunk.get("type")
        return chunk_data, chunk_type

    async def _process_chunk(
        self, chunk: dict[str, Any]
    ) -> AsyncIterator[str | dict[str, Any]]:
        """Process a single chunk from the Claude stream.

        Args:
            chunk: Claude response chunk

        Yields:
            OpenAI-formatted SSE strings or dict objects based on output_format

        """
        from .streaming_handlers import (
            handle_content_block_delta,
            handle_content_block_start,
            handle_content_block_stop,
            handle_message_delta,
            handle_message_start,
            handle_message_stop,
        )

        chunk_data, chunk_type = self._extract_chunk_data(chunk)

        # Dispatch table pattern - handlers that need chunk_data vs those that don't
        handlers_with_data = {
            "content_block_start": handle_content_block_start,
            "content_block_delta": handle_content_block_delta,
            "message_delta": handle_message_delta,
        }
        handlers_without_data = {
            "message_start": handle_message_start,
            "content_block_stop": handle_content_block_stop,
            "message_stop": handle_message_stop,
        }

        if chunk_type in handlers_with_data:
            async for output in handlers_with_data[chunk_type](self, chunk_data):
                yield output
        elif chunk_type in handlers_without_data:
            async for output in handlers_without_data[chunk_type](self):
                yield output

    def _create_chunk_dict(
        self,
        delta: dict[str, Any] | None = None,
        finish_reason: str | None = None,
        usage: dict[str, int] | None = None,
    ) -> dict[str, Any]:
        """Create an OpenAI completion chunk dict.

        Args:
            delta: The delta content for the chunk
            finish_reason: Optional finish reason
            usage: Optional usage information

        Returns:
            OpenAI completion chunk dict

        """
        chunk = {
            "id": self.message_id,
            "object": "chat.completion.chunk",
            "created": self.created,
            "model": self.model,
            "choices": [
                {
                    "index": 0,
                    "delta": delta or {},
                    "logprobs": None,
                    "finish_reason": finish_reason,
                }
            ],
        }

        if usage:
            chunk["usage"] = usage

        return chunk

    def _format_chunk_output(
        self,
        delta: dict[str, Any] | None = None,
        finish_reason: str | None = None,
        usage: dict[str, int] | None = None,
    ) -> str | dict[str, Any]:
        """Format chunk output based on output_format flag.

        Args:
            delta: The delta content for the chunk
            finish_reason: Optional finish reason
            usage: Optional usage information

        Returns:
            Either SSE string or dict based on output_format

        """
        if self.output_format == "dict":
            return self._create_chunk_dict(delta, finish_reason, usage)
        # SSE format
        if finish_reason:
            if usage:
                return self.formatter.format_final_chunk(
                    self.message_id,
                    self.model,
                    self.created,
                    finish_reason,
                    usage=usage,
                )
            return self.formatter.format_final_chunk(
                self.message_id, self.model, self.created, finish_reason
            )
        if delta and delta.get("role"):
            return self.formatter.format_first_chunk(
                self.message_id, self.model, self.created, delta["role"]
            )
        if delta and delta.get("content"):
            return self.formatter.format_content_chunk(
                self.message_id, self.model, self.created, delta["content"]
            )
        if delta and delta.get("tool_calls"):
            # Handle tool calls
            tool_call = delta["tool_calls"][0]  # Assume single tool call for now
            return self.formatter.format_tool_call_chunk(
                self.message_id,
                self.model,
                self.created,
                tool_call["id"],
                tool_call.get("function", {}).get("name"),
                tool_call.get("function", {}).get("arguments"),
            )
        # Empty delta
        return self.formatter.format_final_chunk(
            self.message_id, self.model, self.created, "stop"
        )


__all__ = [
    "OpenAISSEFormatter",
    "OpenAIStreamProcessor",
]
