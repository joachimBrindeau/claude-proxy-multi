"""Options handling for Claude SDK interactions."""

from typing import Any

import structlog

from claude_code_proxy.config.settings import Settings
from claude_code_proxy.core.async_utils import patched_typing


with patched_typing():
    from claude_code_sdk import ClaudeCodeOptions

logger = structlog.get_logger(__name__)


class OptionsHandler:
    """Handles creation and management of Claude SDK options."""

    def __init__(self, settings: Settings | None = None) -> None:
        """Initialize options handler.

        Args:
            settings: Application settings containing default Claude options

        """
        self.settings = settings

    def _create_options_from_config(
        self, configured_opts: ClaudeCodeOptions
    ) -> ClaudeCodeOptions:
        """Create a new ClaudeCodeOptions from an existing configured instance.

        Args:
            configured_opts: Existing configured options

        Returns:
            New ClaudeCodeOptions with copied configuration

        """
        mcp_servers = (
            configured_opts.mcp_servers.copy()
            if isinstance(configured_opts.mcp_servers, dict)
            else {}
        )

        options = ClaudeCodeOptions(
            mcp_servers=mcp_servers,
            permission_prompt_tool_name=configured_opts.permission_prompt_tool_name,
        )

        self._copy_optional_attributes(configured_opts, options)
        return options

    def _copy_optional_attributes(
        self, source: ClaudeCodeOptions, target: ClaudeCodeOptions
    ) -> None:
        """Copy optional attributes from source to target options.

        Args:
            source: Source options to copy from
            target: Target options to copy to

        """
        optional_attrs = [
            ("max_thinking_tokens", int),
            ("allowed_tools", list),
            ("disallowed_tools", list),
            ("cwd", str),
            ("append_system_prompt", str),
            ("max_turns", int),
            ("continue_conversation", bool),
            ("permission_mode", str),
        ]

        for attr_name, converter in optional_attrs:
            value = getattr(source, attr_name, None)
            if value is not None:
                setattr(target, attr_name, converter(value))

    def create_options(
        self,
        model: str,
        temperature: float | None = None,
        max_tokens: int | None = None,
        system_message: str | None = None,
        **additional_options: Any,
    ) -> ClaudeCodeOptions:
        """Create Claude SDK options from API parameters.

        Args:
            model: The model name
            temperature: Temperature for response generation
            max_tokens: Maximum tokens in response
            system_message: System message to include
            **additional_options: Additional options to set on the ClaudeCodeOptions instance

        Returns:
            Configured ClaudeCodeOptions instance

        """
        # Start with configured defaults if available, otherwise create fresh instance
        if self.settings and self.settings.claude.code_options:
            options = self._create_options_from_config(
                self.settings.claude.code_options
            )
        else:
            options = ClaudeCodeOptions()

        # Override the model (API parameter takes precedence)
        options.model = model

        # Apply system message if provided (this is supported by ClaudeCodeOptions)
        if system_message is not None:
            options.system_prompt = system_message

        # If session_id is provided via additional_options, enable continue_conversation
        if additional_options.get("session_id"):
            options.continue_conversation = True

        # Handle additional options as needed
        for key, value in additional_options.items():
            if hasattr(options, key):
                setattr(options, key, value)

        return options

    @staticmethod
    def extract_system_message(messages: list[dict[str, Any]]) -> str | None:
        """Extract system message from Anthropic messages format.

        Args:
            messages: List of messages in Anthropic format

        Returns:
            System message content if found, None otherwise

        """
        for message in messages:
            if message.get("role") == "system":
                content = message.get("content", "")
                if isinstance(content, list):
                    # Handle content blocks
                    text_parts = []
                    for block in content:
                        if block.get("type") == "text":
                            text_parts.append(block.get("text", ""))
                    return " ".join(text_parts)
                return str(content)
        return None

    @staticmethod
    def get_supported_models() -> list[str]:
        """Get list of supported Claude models.

        Returns:
            List of supported model names

        """
        # Import here to avoid circular imports
        from claude_code_proxy.utils.model_mapping import get_supported_claude_models

        # Get supported Claude models
        claude_models = get_supported_claude_models()
        return claude_models

    @staticmethod
    def validate_model(model: str) -> bool:
        """Validate if a model is supported.

        Args:
            model: The model name to validate

        Returns:
            True if supported, False otherwise

        """
        return model in OptionsHandler.get_supported_models()

    @staticmethod
    def get_default_options() -> dict[str, Any]:
        """Get default options for API parameters.

        Returns:
            Dictionary of default API parameter values

        """
        return {
            "model": "claude-3-5-sonnet-20241022",
            "temperature": 0.7,
            "max_tokens": 4000,
        }
