"""Handler functions for OpenAI streaming chunk processing.

This module contains extracted handler functions from the OpenAIStreamProcessor
to reduce complexity and improve maintainability.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any

import orjson


if TYPE_CHECKING:
    from .streaming import OpenAIStreamProcessor


async def handle_message_start(
    processor: OpenAIStreamProcessor,
) -> AsyncIterator[str | dict[str, Any]]:
    """Handle message_start chunk - sends initial role.

    Args:
        processor: The stream processor instance

    Yields:
        Formatted role chunk if not already sent
    """
    if not processor.role_sent:
        yield processor._format_chunk_output(delta={"role": "assistant"})
        processor.role_sent = True
    if False:
        yield  # type: ignore[unreachable]  # noqa: B009


async def handle_content_block_start(
    processor: OpenAIStreamProcessor, chunk_data: dict[str, Any]
) -> AsyncIterator[str | dict[str, Any]]:
    """Handle content_block_start chunk - processes different block types.

    Args:
        processor: The stream processor instance
        chunk_data: The chunk data containing the content block

    Yields:
        Formatted chunks for various content block types
    """
    block = chunk_data.get("content_block", {})
    block_type = block.get("type")

    if block_type == "thinking":
        # Start of thinking block
        processor.thinking_block_active = True
        processor.current_thinking_text = ""
        processor.current_thinking_signature = None

    elif block_type == "system_message":
        # Handle system message content block
        system_text = block.get("text", "")
        source = block.get("source", "claude_code_sdk")
        formatted_text = f"[{source}]: {system_text}"
        yield processor._format_chunk_output(delta={"content": formatted_text})

    elif block_type == "tool_use_sdk" and processor.enable_tool_calls:
        # Handle custom tool_use_sdk content block
        tool_id = block.get("id", "")
        tool_name = block.get("name", "")
        tool_input = block.get("input", {})

        # For dict format, immediately yield the tool call
        if processor.output_format == "dict":
            yield processor._format_chunk_output(
                delta={
                    "tool_calls": [
                        {
                            "index": 0,
                            "id": tool_id,
                            "type": "function",
                            "function": {
                                "name": tool_name,
                                "arguments": orjson.dumps(tool_input).decode(),
                            },
                        }
                    ]
                }
            )
        else:
            # For SSE format, store for later processing
            processor.tool_calls[tool_id] = {
                "id": tool_id,
                "name": tool_name,
                "arguments": tool_input,
                "source": block.get("source", "claude_code_sdk"),
            }

    elif block_type == "tool_result_sdk":
        # Handle custom tool_result_sdk content block
        source = block.get("source", "claude_code_sdk")
        tool_use_id = block.get("tool_use_id", "")
        result_content = block.get("content", "")
        is_error = block.get("is_error", False)
        error_indicator = " (ERROR)" if is_error else ""
        formatted_text = (
            f"[{source} tool_result {tool_use_id}{error_indicator}]: {result_content}"
        )
        yield processor._format_chunk_output(delta={"content": formatted_text})

    elif block_type == "result_message":
        # Handle custom result_message content block
        source = block.get("source", "claude_code_sdk")
        result_data = block.get("data", {})
        session_id = result_data.get("session_id", "")
        stop_reason = result_data.get("stop_reason", "")
        usage = result_data.get("usage", {})
        formatted_text = (
            f"[{source} result {session_id}]: stop_reason={stop_reason}, usage={usage}"
        )
        yield processor._format_chunk_output(delta={"content": formatted_text})

    elif block_type == "tool_use":
        # Start of tool call
        tool_id = block.get("id", "")
        tool_name = block.get("name", "")
        processor.tool_calls[tool_id] = {
            "id": tool_id,
            "name": tool_name,
            "arguments": "",
        }

    if False:
        yield  # type: ignore[unreachable]  # noqa: B009


async def handle_content_block_delta(
    processor: OpenAIStreamProcessor, chunk_data: dict[str, Any]
) -> AsyncIterator[str | dict[str, Any]]:
    """Handle content_block_delta chunk - processes delta updates.

    Args:
        processor: The stream processor instance
        chunk_data: The chunk data containing the delta

    Yields:
        Formatted text chunks
    """
    delta = chunk_data.get("delta", {})
    delta_type = delta.get("type")

    if delta_type == "text_delta":
        # Text content
        text = delta.get("text", "")
        if text:
            yield processor._format_chunk_output(delta={"content": text})

    elif delta_type == "thinking_delta" and processor.thinking_block_active:
        # Thinking content
        thinking_text = delta.get("thinking", "")
        if thinking_text:
            processor.current_thinking_text += thinking_text

    elif delta_type == "signature_delta" and processor.thinking_block_active:
        # Thinking signature
        signature = delta.get("signature", "")
        if signature:
            if processor.current_thinking_signature is None:
                processor.current_thinking_signature = ""
            processor.current_thinking_signature += signature

    elif delta_type == "input_json_delta":
        # Tool call arguments
        partial_json = delta.get("partial_json", "")
        if partial_json and processor.tool_calls:
            # Find the tool call this belongs to (usually the last one)
            latest_tool_id = list(processor.tool_calls.keys())[-1]
            processor.tool_calls[latest_tool_id]["arguments"] += partial_json

    if False:
        yield  # type: ignore[unreachable]  # noqa: B009


async def handle_content_block_stop(
    processor: OpenAIStreamProcessor,
) -> AsyncIterator[str | dict[str, Any]]:
    """Handle content_block_stop chunk - finishes content blocks.

    Args:
        processor: The stream processor instance

    Yields:
        Formatted thinking blocks or tool calls
    """
    # End of content block
    if processor.thinking_block_active:
        # Format and send the complete thinking block
        processor.thinking_block_active = False
        if processor.current_thinking_text:
            # Format thinking block with signature
            thinking_content = f'<thinking signature="{processor.current_thinking_signature}">{processor.current_thinking_text}</thinking>'
            yield processor._format_chunk_output(delta={"content": thinking_content})
        # Reset thinking state
        processor.current_thinking_text = ""
        processor.current_thinking_signature = None

    elif (
        processor.tool_calls
        and processor.enable_tool_calls
        and processor.output_format == "sse"
    ):
        # Send completed tool calls (only for SSE format, dict format sends immediately)
        for tool_call in processor.tool_calls.values():
            yield processor._format_chunk_output(
                delta={
                    "tool_calls": [
                        {
                            "index": 0,
                            "id": tool_call["id"],
                            "type": "function",
                            "function": {
                                "name": tool_call["name"],
                                "arguments": orjson.dumps(
                                    tool_call["arguments"]
                                ).decode()
                                if isinstance(tool_call["arguments"], dict)
                                else tool_call["arguments"],
                            },
                        }
                    ]
                }
            )

    if False:
        yield  # type: ignore[unreachable]  # noqa: B009


async def handle_message_delta(
    processor: OpenAIStreamProcessor, chunk_data: dict[str, Any]
) -> AsyncIterator[str | dict[str, Any]]:
    """Handle message_delta chunk - processes usage information.

    Args:
        processor: The stream processor instance
        chunk_data: The chunk data containing usage info

    Yields:
        Nothing (updates processor state only)
    """
    # Usage information
    usage = chunk_data.get("usage", {})
    if usage and processor.enable_usage:
        processor.usage_info = {
            "prompt_tokens": usage.get("input_tokens", 0),
            "completion_tokens": usage.get("output_tokens", 0),
            "total_tokens": usage.get("input_tokens", 0)
            + usage.get("output_tokens", 0),
        }
    if False:
        yield  # type: ignore[unreachable]  # noqa: B009


async def handle_message_stop(
    processor: OpenAIStreamProcessor,
) -> AsyncIterator[str | dict[str, Any]]:
    """Handle message_stop chunk - end of message.

    Args:
        processor: The stream processor instance

    Yields:
        Nothing (handled in main process_stream method)
    """
    # End of message - handled in main process_stream method
    if False:
        yield  # type: ignore[unreachable]  # noqa: B009
