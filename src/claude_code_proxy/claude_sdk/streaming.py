"""Handles processing of Claude SDK streaming responses."""

from collections.abc import AsyncIterator
from typing import Any
from uuid import uuid4

import structlog

from claude_code_proxy.claude_sdk.converter import MessageConverter
from claude_code_proxy.config.claude import SDKMessageMode
from claude_code_proxy.core.request_context import RequestContext
from claude_code_proxy.models import claude_sdk as sdk_models


logger = structlog.get_logger(__name__)


class ClaudeStreamProcessor:
    """Processes streaming responses from the Claude SDK."""

    def __init__(
        self,
        message_converter: MessageConverter,
    ) -> None:
        """Initialize the stream processor.

        Args:
            message_converter: Converter for message formats.

        """
        self.message_converter = message_converter

    def _handle_system_message(
        self,
        message: sdk_models.SystemMessage,
        sdk_message_mode: SDKMessageMode,
        content_block_index: int,
        pretty_format: bool,
        request_id: str | None,
    ) -> tuple[list[dict[str, Any]], int]:
        """Handle SystemMessage event.

        Returns:
            Tuple of (chunks to yield, updated content_block_index)

        """
        logger.debug(
            "sdk_system_message_processing",
            mode=sdk_message_mode.value,
            subtype=message.subtype,
            request_id=request_id,
        )
        if sdk_message_mode == SDKMessageMode.IGNORE:
            return [], content_block_index

        chunks = self.message_converter._create_sdk_content_block_chunks(
            sdk_object=message,
            mode=sdk_message_mode,
            index=content_block_index,
            pretty_format=pretty_format,
            xml_tag="system_message",
        )
        return [chunk for _, chunk in chunks], content_block_index + 1

    def _handle_text_block(
        self,
        block: sdk_models.TextBlock,
        content_block_index: int,
        request_id: str | None,
    ) -> tuple[list[dict[str, Any]], int]:
        """Handle TextBlock within AssistantMessage.

        Returns:
            Tuple of (chunks to yield, updated content_block_index)

        """
        logger.debug(
            "sdk_text_block_processing",
            text_length=len(block.text),
            text_preview=block.text[:50],
            block_index=content_block_index,
            request_id=request_id,
        )
        chunks = [
            {
                "type": "content_block_start",
                "index": content_block_index,
                "content_block": {"type": "text", "text": ""},
            },
            self.message_converter.create_streaming_delta_chunk(block.text)[1],
            {
                "type": "content_block_stop",
                "index": content_block_index,
            },
        ]
        return chunks, content_block_index + 1

    def _handle_tool_use_block(
        self,
        block: sdk_models.ToolUseBlock,
        sdk_message_mode: SDKMessageMode,
        content_block_index: int,
        pretty_format: bool,
        request_id: str | None,
    ) -> tuple[list[dict[str, Any]], int]:
        """Handle ToolUseBlock within AssistantMessage.

        Returns:
            Tuple of (chunks to yield, updated content_block_index)

        """
        logger.debug(
            "sdk_tool_use_block_processing",
            tool_id=block.id,
            tool_name=block.name,
            input_keys=list(block.input.keys()) if block.input else [],
            block_index=content_block_index,
            mode=sdk_message_mode.value,
            request_id=request_id,
        )
        logger.info(
            "sdk_tool_use_block",
            tool_id=block.id,
            tool_name=block.name,
            input_keys=list(block.input.keys()) if block.input else [],
            block_index=content_block_index,
            mode=sdk_message_mode.value,
            request_id=request_id,
        )
        chunks = self.message_converter._create_sdk_content_block_chunks(
            sdk_object=block,
            mode=sdk_message_mode,
            index=content_block_index,
            pretty_format=pretty_format,
            xml_tag="tool_use_sdk",
            sdk_block_converter=lambda obj: obj.to_sdk_block(),
        )
        return [chunk for _, chunk in chunks], content_block_index + 1

    def _handle_tool_result_block(
        self,
        block: sdk_models.ToolResultBlock,
        sdk_message_mode: SDKMessageMode,
        content_block_index: int,
        pretty_format: bool,
        request_id: str | None,
    ) -> tuple[list[dict[str, Any]], int]:
        """Handle ToolResultBlock within AssistantMessage or UserMessage.

        Returns:
            Tuple of (chunks to yield, updated content_block_index)

        """
        logger.debug(
            "sdk_tool_result_block_processing",
            tool_use_id=block.tool_use_id,
            is_error=block.is_error,
            content_type=type(block.content).__name__ if block.content else "None",
            content_preview=str(block.content)[:100] if block.content else None,
            block_index=content_block_index,
            mode=sdk_message_mode.value,
            request_id=request_id,
        )
        logger.info(
            "sdk_tool_result_block",
            tool_use_id=block.tool_use_id,
            is_error=block.is_error,
            content_type=type(block.content).__name__ if block.content else "None",
            content_preview=str(block.content)[:100] if block.content else None,
            block_index=content_block_index,
            mode=sdk_message_mode.value,
            request_id=request_id,
        )
        chunks = self.message_converter._create_sdk_content_block_chunks(
            sdk_object=block,
            mode=sdk_message_mode,
            index=content_block_index,
            pretty_format=pretty_format,
            xml_tag="tool_result_sdk",
            sdk_block_converter=lambda obj: obj.to_sdk_block(),
        )
        return [chunk for _, chunk in chunks], content_block_index + 1

    def _handle_assistant_message(
        self,
        message: sdk_models.AssistantMessage,
        sdk_message_mode: SDKMessageMode,
        content_block_index: int,
        pretty_format: bool,
        request_id: str | None,
    ) -> tuple[list[dict[str, Any]], int]:
        """Handle AssistantMessage event.

        Returns:
            Tuple of (chunks to yield, updated content_block_index)

        """
        logger.debug(
            "sdk_assistant_message_processing",
            content_blocks_count=len(message.content),
            block_types=[type(block).__name__ for block in message.content],
            request_id=request_id,
        )
        chunks = []
        for block in message.content:
            if isinstance(block, sdk_models.TextBlock):
                block_chunks, content_block_index = self._handle_text_block(
                    block, content_block_index, request_id
                )
                chunks.extend(block_chunks)
            elif isinstance(block, sdk_models.ToolUseBlock):
                block_chunks, content_block_index = self._handle_tool_use_block(
                    block,
                    sdk_message_mode,
                    content_block_index,
                    pretty_format,
                    request_id,
                )
                chunks.extend(block_chunks)
            elif isinstance(block, sdk_models.ToolResultBlock):
                block_chunks, content_block_index = self._handle_tool_result_block(
                    block,
                    sdk_message_mode,
                    content_block_index,
                    pretty_format,
                    request_id,
                )
                chunks.extend(block_chunks)
        return chunks, content_block_index

    def _handle_user_message(
        self,
        message: sdk_models.UserMessage,
        sdk_message_mode: SDKMessageMode,
        content_block_index: int,
        pretty_format: bool,
        request_id: str | None,
    ) -> tuple[list[dict[str, Any]], int]:
        """Handle UserMessage event.

        Returns:
            Tuple of (chunks to yield, updated content_block_index)

        """
        logger.debug(
            "sdk_user_message_processing",
            content_blocks_count=len(message.content),
            block_types=[type(block).__name__ for block in message.content],
            request_id=request_id,
        )
        chunks = []
        for block in message.content:
            if isinstance(block, sdk_models.ToolResultBlock):
                block_chunks, content_block_index = self._handle_tool_result_block(
                    block,
                    sdk_message_mode,
                    content_block_index,
                    pretty_format,
                    request_id,
                )
                chunks.extend(block_chunks)
            else:
                logger.debug(
                    "sdk_user_message_unsupported_block",
                    block_type=type(block).__name__,
                    block_index=content_block_index,
                    request_id=request_id,
                )
        return chunks, content_block_index

    def _handle_result_message(
        self,
        message: sdk_models.ResultMessage,
        sdk_message_mode: SDKMessageMode,
        content_block_index: int,
        pretty_format: bool,
        ctx: RequestContext | None,
        request_id: str | None,
    ) -> tuple[list[dict[str, Any]], bool]:
        """Handle ResultMessage event.

        Returns:
            Tuple of (chunks to yield, should_break flag)

        """
        logger.debug(
            "sdk_result_message_processing",
            session_id=message.session_id,
            stop_reason=message.stop_reason,
            is_error=message.is_error,
            duration_ms=message.duration_ms,
            num_turns=message.num_turns,
            usage_available=message.usage is not None,
            mode=sdk_message_mode.value,
            request_id=request_id,
        )
        chunks = []

        if sdk_message_mode != SDKMessageMode.IGNORE:
            sdk_chunks = self.message_converter._create_sdk_content_block_chunks(
                sdk_object=message,
                mode=sdk_message_mode,
                index=content_block_index,
                pretty_format=pretty_format,
                xml_tag="system_message",
            )
            chunks.extend([chunk for _, chunk in sdk_chunks])

            if ctx:
                usage_model = message.usage_model
                ctx.add_metadata(
                    status_code=200,
                    tokens_input=usage_model.input_tokens,
                    tokens_output=usage_model.output_tokens,
                    cache_read_tokens=usage_model.cache_read_input_tokens,
                    cache_write_tokens=usage_model.cache_creation_input_tokens,
                    session_id=message.session_id,
                    num_turns=message.num_turns,
                )

        end_chunks = self.message_converter.create_streaming_end_chunks(
            stop_reason=message.stop_reason
        )
        # Update usage in the delta chunk
        delta_chunk = end_chunks[0][1]
        delta_chunk["usage"] = {"output_tokens": message.usage_model.output_tokens}

        chunks.append(delta_chunk)
        chunks.append(end_chunks[1][1])  # message_stop
        return chunks, True

    async def process_stream(
        self,
        sdk_stream: AsyncIterator[
            sdk_models.UserMessage
            | sdk_models.AssistantMessage
            | sdk_models.SystemMessage
            | sdk_models.ResultMessage
        ],
        model: str,
        request_id: str | None,
        ctx: RequestContext | None,
        sdk_message_mode: SDKMessageMode,
        pretty_format: bool,
    ) -> AsyncIterator[dict[str, Any]]:
        """Process the SDK stream and yields Anthropic-compatible streaming chunks.

        Args:
            sdk_stream: The async iterator of Pydantic SDK messages.
            model: The model name.
            request_id: The request ID for correlation.
            ctx: The request context for observability.
            sdk_message_mode: The mode for handling system messages.
            pretty_format: Whether to format content prettily.

        Yields:
            Anthropic-compatible streaming chunks.

        """
        message_id = f"msg_{uuid4()}"
        content_block_index = 0
        input_tokens = 0  # Will be updated by ResultMessage

        # Yield start chunks
        start_chunks = self.message_converter.create_streaming_start_chunks(
            message_id, model, input_tokens
        )
        for _, chunk in start_chunks:
            yield chunk

        async for message in sdk_stream:
            logger.debug(
                "sdk_message_received",
                message_type=type(message).__name__,
                request_id=request_id,
                message_content=message.model_dump()
                if hasattr(message, "model_dump")
                else str(message)[:200],
            )

            # Dispatch to appropriate handler
            chunks: list[dict[str, Any]] = []
            should_break = False

            if isinstance(message, sdk_models.SystemMessage):
                chunks, content_block_index = self._handle_system_message(
                    message,
                    sdk_message_mode,
                    content_block_index,
                    pretty_format,
                    request_id,
                )
            elif isinstance(message, sdk_models.AssistantMessage):
                chunks, content_block_index = self._handle_assistant_message(
                    message,
                    sdk_message_mode,
                    content_block_index,
                    pretty_format,
                    request_id,
                )
            elif isinstance(message, sdk_models.UserMessage):
                chunks, content_block_index = self._handle_user_message(
                    message,
                    sdk_message_mode,
                    content_block_index,
                    pretty_format,
                    request_id,
                )
            elif isinstance(message, sdk_models.ResultMessage):
                chunks, should_break = self._handle_result_message(
                    message,
                    sdk_message_mode,
                    content_block_index,
                    pretty_format,
                    ctx,
                    request_id,
                )
            else:
                logger.warning(  # type: ignore[unreachable]
                    "sdk_unknown_message_type",
                    message_type=type(message).__name__,
                    message_content=str(message)[:200],
                    request_id=request_id,
                )

            # Yield all chunks from handler
            for chunk in chunks:
                yield chunk

            if should_break:
                break  # End of stream
        else:
            # Stream ended without a ResultMessage - this indicates an error/interruption
            if ctx and "status_code" not in ctx.metadata:
                # Set error status if not already set (e.g., by StreamTimeoutError handler)
                logger.warning(
                    "stream_ended_without_result_message",
                    request_id=request_id,
                    message="Stream ended without ResultMessage, likely interrupted",
                )
                ctx.add_metadata(
                    status_code=499,  # Client Closed Request
                    error_type="stream_interrupted",
                    error_message="Stream ended without completion",
                )

        # Final message, contains metrics
        # NOTE: Access logging is now handled by StreamingResponseWithLogging
        # No need for manual access logging here anymore

        logger.debug("claude_sdk_stream_processing_completed", request_id=request_id)
