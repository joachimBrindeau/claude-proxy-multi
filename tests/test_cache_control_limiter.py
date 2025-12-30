"""Tests for cache control limiting functionality."""

import importlib
import json
import sys


# Force reload to get latest changes
if "ccproxy.core.http_transformers" in sys.modules:
    importlib.reload(sys.modules["ccproxy.core.http_transformers"])

from claude_code_proxy.core.http_transformers import HTTPRequestTransformer


class TestCacheControlLimiter:
    """Test cache control limiting in request transformation."""

    def setup_method(self):
        """Set up test fixtures."""
        self.transformer = HTTPRequestTransformer()

    def test_count_cache_control_blocks(self):
        """Test counting cache_control blocks in different parts of request."""
        data = {
            "system": [
                {
                    "type": "text",
                    "text": "You are Claude Code, Anthropic's official CLI",
                    "cache_control": {"type": "ephemeral"},
                },
                {
                    "type": "text",
                    "text": "User's system prompt",
                    "cache_control": {"type": "ephemeral"},
                },
            ],
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Hello",
                            "cache_control": {"type": "ephemeral"},
                        },
                        {
                            "type": "text",
                            "text": "World",
                            "cache_control": {"type": "ephemeral"},
                        },
                    ],
                }
            ],
        }

        counts = self.transformer._count_cache_control_blocks(data)

        assert counts["injected_system"] == 1  # Claude Code prompt
        assert counts["user_system"] == 1  # User's system prompt
        assert counts["messages"] == 2  # Two message blocks

    def test_no_limiting_when_under_limit(self):
        """Test that requests with ≤4 cache_control blocks pass through unchanged."""
        data = {
            "system": [
                {
                    "type": "text",
                    "text": "You are Claude Code, Anthropic's official CLI",
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Hello",
                            "cache_control": {"type": "ephemeral"},
                        }
                    ],
                }
            ],
        }

        result = self.transformer._limit_cache_control_blocks(data)

        # Should be unchanged
        assert result == data

        # Verify cache_control still present
        assert "cache_control" in result["system"][0]
        assert "cache_control" in result["messages"][0]["content"][0]

    def test_remove_message_cache_control_first(self):
        """Test that message cache_control blocks are removed first (lowest priority)."""
        data = {
            "system": [
                {
                    "type": "text",
                    "text": "You are Claude Code, Anthropic's official CLI",
                    "cache_control": {"type": "ephemeral"},
                },
                {
                    "type": "text",
                    "text": "User system prompt",
                    "cache_control": {"type": "ephemeral"},
                },
            ],
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Block 1",
                            "cache_control": {"type": "ephemeral"},
                        },
                        {
                            "type": "text",
                            "text": "Block 2",
                            "cache_control": {"type": "ephemeral"},
                        },
                        {
                            "type": "text",
                            "text": "Block 3",
                            "cache_control": {"type": "ephemeral"},
                        },
                        {
                            "type": "text",
                            "text": "Block 4",
                            "cache_control": {"type": "ephemeral"},
                        },
                    ],
                }
            ],
        }

        # Total: 6 blocks (2 system + 4 messages), need to remove 2
        result = self.transformer._limit_cache_control_blocks(data)

        # System prompts should be preserved
        assert "cache_control" in result["system"][0]  # Injected
        assert "cache_control" in result["system"][1]  # User system

        # Check that exactly 2 message blocks were removed
        message_blocks_with_cache = [
            block
            for block in result["messages"][0]["content"]
            if "cache_control" in block
        ]
        assert len(message_blocks_with_cache) == 2  # 4 - 2 = 2 remaining

    def test_remove_user_system_before_injected(self):
        """Test that user system cache_control is removed before injected system."""
        data = {
            "system": [
                {
                    "type": "text",
                    "text": "You are Claude Code, Anthropic's official CLI",
                    "cache_control": {"type": "ephemeral"},
                },
                {
                    "type": "text",
                    "text": "User system 1",
                    "cache_control": {"type": "ephemeral"},
                },
                {
                    "type": "text",
                    "text": "User system 2",
                    "cache_control": {"type": "ephemeral"},
                },
                {
                    "type": "text",
                    "text": "User system 3",
                    "cache_control": {"type": "ephemeral"},
                },
                {
                    "type": "text",
                    "text": "User system 4",
                    "cache_control": {"type": "ephemeral"},
                },
            ],
            "messages": [],
        }

        # Total: 5 blocks, need to remove 1
        result = self.transformer._limit_cache_control_blocks(data)

        # Injected prompt should always be preserved
        assert "cache_control" in result["system"][0]

        # Count remaining cache_control blocks in user system prompts
        user_system_with_cache = [
            block
            for i, block in enumerate(result["system"][1:], 1)
            if "cache_control" in block
        ]
        assert len(user_system_with_cache) == 3  # 4 - 1 = 3 remaining

    def test_preserve_injected_system_priority(self):
        """Test that injected system prompt cache_control has highest priority."""
        data = {
            "system": [
                {
                    "type": "text",
                    "text": "You are Claude Code, Anthropic's official CLI for Claude.",
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "M1",
                            "cache_control": {"type": "ephemeral"},
                        },
                        {
                            "type": "text",
                            "text": "M2",
                            "cache_control": {"type": "ephemeral"},
                        },
                        {
                            "type": "text",
                            "text": "M3",
                            "cache_control": {"type": "ephemeral"},
                        },
                        {
                            "type": "text",
                            "text": "M4",
                            "cache_control": {"type": "ephemeral"},
                        },
                        {
                            "type": "text",
                            "text": "M5",
                            "cache_control": {"type": "ephemeral"},
                        },
                    ],
                }
            ],
        }

        # Total: 6 blocks (1 injected + 5 messages), need to remove 2
        result = self.transformer._limit_cache_control_blocks(data)

        # Injected prompt must be preserved
        assert "cache_control" in result["system"][0]
        assert "Claude Code" in result["system"][0]["text"]

        # Exactly 3 message blocks should remain (5 - 2)
        message_blocks_with_cache = [
            block
            for block in result["messages"][0]["content"]
            if "cache_control" in block
        ]
        assert len(message_blocks_with_cache) == 3

    def test_transform_system_prompt_with_limiting(self):
        """Test that transform_system_prompt applies cache_control limiting."""
        # Create a request body with too many cache_control blocks
        request_data = {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Q1",
                            "cache_control": {"type": "ephemeral"},
                        },
                        {
                            "type": "text",
                            "text": "Q2",
                            "cache_control": {"type": "ephemeral"},
                        },
                        {
                            "type": "text",
                            "text": "Q3",
                            "cache_control": {"type": "ephemeral"},
                        },
                        {
                            "type": "text",
                            "text": "Q4",
                            "cache_control": {"type": "ephemeral"},
                        },
                    ],
                }
            ]
        }

        body = json.dumps(request_data).encode("utf-8")

        # Transform with system prompt injection
        result_body = self.transformer.transform_system_prompt(body)
        result_data = json.loads(result_body.decode("utf-8"))

        # Count total cache_control blocks
        total_cache_control = 0

        # Count in system
        if "system" in result_data:
            system = result_data["system"]
            if isinstance(system, list):
                for block in system:
                    if isinstance(block, dict) and "cache_control" in block:
                        total_cache_control += 1

        # Count in messages
        for msg in result_data.get("messages", []):
            content = msg.get("content", [])
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and "cache_control" in block:
                        total_cache_control += 1

        # Should not exceed 4
        assert total_cache_control <= 4, (
            f"Total cache_control blocks: {total_cache_control}"
        )
