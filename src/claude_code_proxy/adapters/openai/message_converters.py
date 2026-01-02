"""Message conversion helpers for OpenAI to Anthropic format.

This module provides focused converter functions for each message type,
reducing complexity in the main adapter.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import structlog


logger = structlog.get_logger(__name__)


def convert_system_message(msg: Any, current_system_prompt: str | None) -> str:
    """Convert system or developer message to system prompt.

    Args:
        msg: OpenAI message object
        current_system_prompt: Existing system prompt to append to

    Returns:
        Updated system prompt
    """
    if isinstance(msg.content, str):
        new_content = msg.content
    elif isinstance(msg.content, list):
        # Extract text from content blocks
        text_parts: list[str] = []
        for block in msg.content:
            if (
                hasattr(block, "type")
                and block.type == "text"
                and hasattr(block, "text")
                and block.text
            ):
                text_parts.append(block.text)
        new_content = " ".join(text_parts)
    else:
        return current_system_prompt or ""

    if current_system_prompt:
        return f"{current_system_prompt}\n{new_content}"
    return new_content


def convert_user_or_assistant_message(
    msg: Any,
    convert_content_fn: Callable[[Any], str | list[dict[str, Any]]],
    convert_tool_call_fn: Callable[[Any], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Convert user or assistant message to Anthropic format.

    Args:
        msg: OpenAI message object
        convert_content_fn: Function to convert content
        convert_tool_call_fn: Function to convert tool calls (optional)

    Returns:
        Anthropic format message
    """
    anthropic_msg = {
        "role": msg.role,
        "content": convert_content_fn(msg.content),
    }

    # Add tool calls if present
    if hasattr(msg, "tool_calls") and msg.tool_calls and convert_tool_call_fn:
        anthropic_msg = _add_tool_calls_to_message(
            anthropic_msg, msg.tool_calls, convert_tool_call_fn
        )

    return anthropic_msg


def _add_tool_calls_to_message(
    anthropic_msg: dict[str, Any],
    tool_calls: list[Any],
    convert_tool_call_fn: Callable[[Any], dict[str, Any]],
) -> dict[str, Any]:
    """Add tool calls to an Anthropic message.

    Args:
        anthropic_msg: Anthropic message dict
        tool_calls: List of OpenAI tool calls
        convert_tool_call_fn: Function to convert tool calls

    Returns:
        Updated message with tool calls
    """
    # Ensure content is a list
    if isinstance(anthropic_msg["content"], str):
        anthropic_msg["content"] = [{"type": "text", "text": anthropic_msg["content"]}]
    if not isinstance(anthropic_msg["content"], list):
        anthropic_msg["content"] = []

    # Content is now guaranteed to be a list
    content_list = anthropic_msg["content"]
    for tool_call in tool_calls:
        content_list.append(convert_tool_call_fn(tool_call))

    return anthropic_msg


def convert_tool_message(
    msg: Any, messages: list[dict[str, Any]]
) -> dict[str, Any] | None:
    """Convert tool result message to Anthropic format.

    Args:
        msg: OpenAI tool message
        messages: Existing messages list (to check for appending)

    Returns:
        New message dict or None if appended to existing message
    """
    tool_result = {
        "type": "tool_result",
        "tool_use_id": getattr(msg, "tool_call_id", "unknown") or "unknown",
        "content": msg.content or "",
    }

    # If last message is user, append to it
    if messages and messages[-1]["role"] == "user":
        _append_tool_result_to_last_message(messages, tool_result)
        return None

    # Otherwise create new user message
    return {
        "role": "user",
        "content": [tool_result],
    }


def _append_tool_result_to_last_message(
    messages: list[dict[str, Any]], tool_result: dict[str, Any]
) -> None:
    """Append tool result to last message in list.

    Args:
        messages: Messages list to modify
        tool_result: Tool result to append
    """
    if isinstance(messages[-1]["content"], str):
        messages[-1]["content"] = [{"type": "text", "text": messages[-1]["content"]}]

    if isinstance(messages[-1]["content"], list):
        messages[-1]["content"].append(tool_result)


def convert_messages_dispatcher(
    openai_messages: list[Any],
    convert_content_fn: Callable[[Any], str | list[dict[str, Any]]],
    convert_tool_call_fn: Callable[[Any], dict[str, Any]],
) -> tuple[list[dict[str, Any]], str | None]:
    """Convert OpenAI messages to Anthropic format using dispatcher pattern.

    Args:
        openai_messages: List of OpenAI messages
        convert_content_fn: Function to convert content
        convert_tool_call_fn: Function to convert tool calls

    Returns:
        Tuple of (anthropic messages, system prompt)
    """
    messages: list[dict[str, Any]] = []
    system_prompt: str | None = None

    for openai_msg in openai_messages:
        if openai_msg.role in ["system", "developer"]:
            system_prompt = convert_system_message(openai_msg, system_prompt)
        elif openai_msg.role in ["user", "assistant"]:
            anthropic_msg = convert_user_or_assistant_message(
                openai_msg, convert_content_fn, convert_tool_call_fn
            )
            messages.append(anthropic_msg)
        elif openai_msg.role == "tool":
            result = convert_tool_message(openai_msg, messages)
            if result is not None:
                messages.append(result)

    return messages, system_prompt


# Content block type dispatcher for response conversion
CONTENT_BLOCK_HANDLERS: dict[str, Any] = {
    "text": lambda block, content, tool_calls: (
        content + block.get("text", ""),
        tool_calls,
    ),
    "system_message": lambda block, content, tool_calls: (
        content
        + f"[{block.get('source', 'claude_code_sdk')}]: {block.get('text', '')}",
        tool_calls,
    ),
    "result_message": lambda block, content, tool_calls: (
        content
        + _format_result_message(
            block.get("source", "claude_code_sdk"),
            block.get("data", {}),
        ),
        tool_calls,
    ),
    "thinking": lambda block, content, tool_calls: (
        content
        + f'<thinking signature="{block.get("signature")}">{block.get("thinking", "")}</thinking>\n',
        tool_calls,
    ),
}


def _format_result_message(source: str, data: dict[str, Any]) -> str:
    """Format result message block.

    Args:
        source: Message source
        data: Result data

    Returns:
        Formatted message string
    """
    session_id = data.get("session_id", "")
    stop_reason = data.get("stop_reason", "")
    usage = data.get("usage", {})
    return f"[{source} result {session_id}]: stop_reason={stop_reason}, usage={usage}"


def handle_tool_use_sdk(
    block: dict[str, Any], format_tool_call_fn: Callable[[dict[str, Any]], Any]
) -> Any:
    """Handle tool_use_sdk content block.

    Args:
        block: Tool use SDK block
        format_tool_call_fn: Function to format tool call

    Returns:
        Formatted tool call
    """
    tool_call_block = {
        "type": "tool_use",
        "id": block.get("id", ""),
        "name": block.get("name", ""),
        "input": block.get("input", {}),
    }
    return format_tool_call_fn(tool_call_block)


def handle_tool_result_sdk(block: dict[str, Any]) -> str:
    """Handle tool_result_sdk content block.

    Args:
        block: Tool result SDK block

    Returns:
        Formatted result string
    """
    source = block.get("source", "claude_code_sdk")
    tool_use_id = block.get("tool_use_id", "")
    result_content = block.get("content", "")
    is_error = block.get("is_error", False)
    error_indicator = " (ERROR)" if is_error else ""
    return f"[{source} tool_result {tool_use_id}{error_indicator}]: {result_content}"


def convert_content_blocks_dispatcher(
    response: dict[str, Any], format_tool_call_fn: Callable[[dict[str, Any]], Any]
) -> tuple[str, list[Any]]:
    """Convert Anthropic content blocks using dispatcher pattern.

    Args:
        response: Anthropic response
        format_tool_call_fn: Function to format tool calls

    Returns:
        Tuple of (content string, tool calls list)
    """
    content = ""
    tool_calls: list[Any] = []

    if "content" not in response or not response["content"]:
        return content, tool_calls

    for block in response["content"]:
        block_type = block.get("type")

        # Handle standard content blocks via dispatcher
        if block_type in CONTENT_BLOCK_HANDLERS:
            handler = CONTENT_BLOCK_HANDLERS[block_type]
            content, tool_calls = handler(block, content, tool_calls)

        # Handle tool-related blocks
        elif block_type == "tool_use_sdk":
            tool_calls.append(handle_tool_use_sdk(block, format_tool_call_fn))
        elif block_type == "tool_result_sdk":
            content += handle_tool_result_sdk(block)
        elif block_type == "tool_use":
            tool_calls.append(format_tool_call_fn(block))
        else:
            logger.warning("unsupported_content_block_type", type=block_type)

    return content, tool_calls


__all__ = [
    "convert_system_message",
    "convert_user_or_assistant_message",
    "convert_tool_message",
    "convert_messages_dispatcher",
    "convert_content_blocks_dispatcher",
]
