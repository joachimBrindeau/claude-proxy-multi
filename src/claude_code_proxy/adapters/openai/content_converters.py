"""Content conversion helpers for OpenAI to Anthropic format."""

from __future__ import annotations

import re
from typing import Any

import structlog


logger = structlog.get_logger(__name__)


def parse_thinking_blocks(content: str) -> list[dict[str, Any]]:
    """Parse thinking blocks from string content.

    Args:
        content: String containing thinking blocks

    Returns:
        List of content blocks with thinking and text
    """
    thinking_pattern = r'<thinking signature="([^"]*)">(.*?)</thinking>'
    anthropic_content: list[dict[str, Any]] = []
    last_end = 0

    for match in re.finditer(thinking_pattern, content, re.DOTALL):
        # Add any text before the thinking block
        if match.start() > last_end:
            text_before = content[last_end : match.start()].strip()
            if text_before:
                anthropic_content.append({"type": "text", "text": text_before})

        # Add the thinking block
        signature = match.group(1)
        thinking_text = match.group(2)
        thinking_block: dict[str, Any] = {
            "type": "thinking",
            "thinking": thinking_text,
        }
        if signature and signature != "None":
            thinking_block["signature"] = signature
        anthropic_content.append(thinking_block)

        last_end = match.end()

    # Add any remaining text after the last thinking block
    if last_end < len(content):
        remaining_text = content[last_end:].strip()
        if remaining_text:
            anthropic_content.append({"type": "text", "text": remaining_text})

    return anthropic_content


def convert_image_url_to_anthropic(url: str) -> dict[str, Any] | None:
    """Convert image URL to Anthropic format.

    Args:
        url: Image URL (data: or http://)

    Returns:
        Anthropic image block or None if invalid
    """
    if url.startswith("data:"):
        # Base64 encoded image
        try:
            media_type, data = url.split(";base64,")
            media_type = media_type.split(":")[1]
            return {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": media_type,
                    "data": data,
                },
            }
        except ValueError:
            logger.warning(
                "invalid_base64_image_url",
                url=url[:100] + "..." if len(url) > 100 else url,
                operation="convert_image_url",
            )
            return None
    else:
        # URL-based image (not directly supported by Anthropic)
        return {"type": "text", "text": f"[Image: {url}]"}


def convert_pydantic_block(block: Any) -> dict[str, Any] | None:
    """Convert Pydantic content block to Anthropic format.

    Args:
        block: Pydantic content block object

    Returns:
        Anthropic content block or None if unsupported
    """
    block_type = getattr(block, "type", None)

    if block_type == "text" and hasattr(block, "text") and block.text is not None:
        return {"type": "text", "text": block.text}

    elif (
        block_type == "image_url"
        and hasattr(block, "image_url")
        and block.image_url is not None
    ):
        # Get URL from image_url
        if hasattr(block.image_url, "url"):
            url = block.image_url.url
        elif isinstance(block.image_url, dict):
            url = block.image_url.get("url", "")
        else:
            url = ""

        return convert_image_url_to_anthropic(url)

    return None


def convert_dict_block(block: dict[str, Any]) -> dict[str, Any] | None:
    """Convert dict content block to Anthropic format.

    Args:
        block: Dictionary content block

    Returns:
        Anthropic content block or None if unsupported
    """
    if block.get("type") == "text":
        return {"type": "text", "text": block.get("text", "")}

    elif block.get("type") == "image_url":
        # Convert image URL to Anthropic format
        image_url = block.get("image_url", {})
        url = image_url.get("url", "")
        return convert_image_url_to_anthropic(url)

    return None
