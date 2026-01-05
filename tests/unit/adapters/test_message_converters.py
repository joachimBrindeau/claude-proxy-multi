"""Tests for OpenAI message converters."""

from unittest.mock import Mock

import pytest

from claude_code_proxy.adapters.openai.message_converters import (
    convert_content_blocks_dispatcher,
    convert_messages_dispatcher,
    convert_system_message,
    convert_tool_message,
    convert_user_or_assistant_message,
)


def test_convert_system_message_with_string_content():
    """Test converting system message with string content."""
    msg = Mock()
    msg.content = "Hello, I am a system message"

    result = convert_system_message(msg, None)

    assert result == "Hello, I am a system message"


def test_convert_system_message_appends_to_existing():
    """Test that system messages are appended to existing prompt."""
    msg = Mock()
    msg.content = "Second message"

    result = convert_system_message(msg, "First message")

    assert result == "First message\nSecond message"


def test_convert_user_message():
    """Test converting user message."""
    msg = Mock()
    msg.role = "user"
    msg.content = "Hello"
    msg.tool_calls = None

    convert_content_fn = Mock(return_value="Hello")

    result = convert_user_or_assistant_message(msg, convert_content_fn)

    assert result == {"role": "user", "content": "Hello"}
    convert_content_fn.assert_called_once_with("Hello")


def test_convert_tool_message_creates_new():
    """Test converting tool message creates new message."""
    msg = Mock()
    msg.tool_call_id = "tool_123"
    msg.content = "Tool result"

    result = convert_tool_message(msg, [])

    assert result == {
        "role": "user",
        "content": [
            {
                "type": "tool_result",
                "tool_use_id": "tool_123",
                "content": "Tool result",
            }
        ],
    }


def test_convert_tool_message_appends_to_last_user():
    """Test converting tool message appends to last user message."""
    messages = [{"role": "user", "content": "Hello"}]
    msg = Mock()
    msg.tool_call_id = "tool_123"
    msg.content = "Tool result"

    result = convert_tool_message(msg, messages)

    assert result is None
    assert len(messages) == 1
    # Content is converted from string to list by convert_tool_message
    assert messages[0]["content"] == [  # type: ignore[comparison-overlap]
        {"type": "text", "text": "Hello"},
        {"type": "tool_result", "tool_use_id": "tool_123", "content": "Tool result"},
    ]


def test_convert_messages_dispatcher():
    """Test full message conversion dispatcher."""
    msg1 = Mock()
    msg1.role = "system"
    msg1.content = "You are helpful"

    msg2 = Mock()
    msg2.role = "user"
    msg2.content = "Hello"
    msg2.tool_calls = None

    convert_content_fn = Mock(return_value="Hello")
    convert_tool_call_fn = Mock()

    messages, system_prompt = convert_messages_dispatcher(
        [msg1, msg2], convert_content_fn, convert_tool_call_fn
    )

    assert system_prompt == "You are helpful"
    assert len(messages) == 1
    assert messages[0] == {"role": "user", "content": "Hello"}


def test_convert_content_blocks_dispatcher_text():
    """Test content blocks dispatcher with text block."""
    response = {"content": [{"type": "text", "text": "Hello world"}]}

    format_tool_call_fn = Mock()

    content, tool_calls = convert_content_blocks_dispatcher(
        response, format_tool_call_fn
    )

    assert content == "Hello world"
    assert tool_calls == []


def test_convert_content_blocks_dispatcher_tool_use():
    """Test content blocks dispatcher with tool use."""
    response = {
        "content": [
            {
                "type": "tool_use",
                "id": "tool_123",
                "name": "get_weather",
                "input": {"city": "Paris"},
            }
        ]
    }

    mock_tool_call = {"id": "tool_123", "type": "function"}
    format_tool_call_fn = Mock(return_value=mock_tool_call)

    content, tool_calls = convert_content_blocks_dispatcher(
        response, format_tool_call_fn
    )

    assert content == ""
    assert len(tool_calls) == 1
    assert tool_calls[0] == mock_tool_call


def test_convert_content_blocks_dispatcher_thinking():
    """Test content blocks dispatcher with thinking block."""
    response = {
        "content": [
            {
                "type": "thinking",
                "thinking": "Let me think about this",
                "signature": "sig123",
            }
        ]
    }

    format_tool_call_fn = Mock()

    content, tool_calls = convert_content_blocks_dispatcher(
        response, format_tool_call_fn
    )

    assert '<thinking signature="sig123">Let me think about this</thinking>' in content
    assert tool_calls == []
