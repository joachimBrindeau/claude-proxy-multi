"""Verbose logging service for API requests and responses.

This module provides structured logging for debugging and monitoring
API traffic, including Codex and standard Claude API requests.
"""

import json
import time
from typing import TYPE_CHECKING, Any

import structlog

from ccproxy.services.request_metadata import redact_sensitive_headers
from ccproxy.utils.simple_request_logger import append_streaming_log, write_request_log

if TYPE_CHECKING:
    from ccproxy.observability.context import RequestContext
    from ccproxy.services.proxy_service import RequestData

logger = structlog.get_logger(__name__)


class VerboseLogger:
    """Handles verbose logging for API requests and responses.

    This class encapsulates all verbose logging functionality, providing
    consistent formatting and redaction of sensitive data.
    """

    def __init__(
        self,
        verbose_api: bool = False,
        verbose_streaming: bool = False,
    ) -> None:
        """Initialize the verbose logger.

        Args:
            verbose_api: Enable verbose API request/response logging
            verbose_streaming: Enable verbose streaming chunk logging
        """
        self.verbose_api = verbose_api
        self.verbose_streaming = verbose_streaming

    async def log_api_request(
        self, request_data: "RequestData", ctx: "RequestContext"
    ) -> None:
        """Log details of an outgoing API request if verbose logging is enabled.

        Args:
            request_data: Transformed request data
            ctx: Request context for observability
        """
        if not self.verbose_api:
            return

        body = request_data.get("body")
        body_preview = ""
        full_body = None
        if body:
            try:
                full_body = body.decode("utf-8", errors="replace")
                # Truncate at 1024 chars for readability
                body_preview = full_body[:1024]
                # Try to parse as JSON for better formatting
                try:
                    full_body = json.loads(full_body)
                except json.JSONDecodeError:
                    pass  # Keep as string
            except Exception:
                body_preview = f"<binary data of length {len(body)}>"

        logger.info(
            "verbose_api_request",
            method=request_data["method"],
            url=request_data["url"],
            headers=redact_sensitive_headers(request_data["headers"]),
            body_size=len(body) if body else 0,
            body_preview=body_preview,
        )

        # Use new request logging system
        request_id = ctx.request_id
        timestamp = ctx.get_log_timestamp_prefix()
        await write_request_log(
            request_id=request_id,
            log_type="upstream_request",
            data={
                "method": request_data["method"],
                "url": request_data["url"],
                "headers": dict(request_data["headers"]),  # Don't redact in file
                "body": full_body,
            },
            timestamp=timestamp,
        )

    async def log_api_response(
        self,
        status_code: int,
        headers: dict[str, str],
        body: bytes,
        ctx: "RequestContext",
    ) -> None:
        """Log details of a received API response if verbose logging is enabled.

        Args:
            status_code: HTTP status code
            headers: Response headers
            body: Response body bytes
            ctx: Request context for observability
        """
        if not self.verbose_api:
            return

        body_preview = ""
        if body:
            try:
                # Truncate at 1024 chars for readability
                body_preview = body.decode("utf-8", errors="replace")[:1024]
            except Exception:
                body_preview = f"<binary data of length {len(body)}>"

        logger.info(
            "verbose_api_response",
            status_code=status_code,
            headers=redact_sensitive_headers(headers),
            body_size=len(body),
            body_preview=body_preview,
        )

        # Use new request logging system
        full_body = None
        if body:
            try:
                full_body_str = body.decode("utf-8", errors="replace")
                # Try to parse as JSON for better formatting
                try:
                    full_body = json.loads(full_body_str)
                except json.JSONDecodeError:
                    full_body = full_body_str
            except Exception:
                full_body = f"<binary data of length {len(body)}>"

        # Use new request logging system
        request_id = ctx.request_id
        timestamp = ctx.get_log_timestamp_prefix()
        await write_request_log(
            request_id=request_id,
            log_type="upstream_response",
            data={
                "status_code": status_code,
                "headers": dict(headers),  # Don't redact in file
                "body": full_body,
            },
            timestamp=timestamp,
        )

    async def log_codex_request(
        self,
        request_id: str,
        method: str,
        url: str,
        headers: dict[str, str],
        body_data: dict[str, Any] | None,
        session_id: str,
    ) -> None:
        """Log outgoing Codex request preserving instructions field exactly.

        Args:
            request_id: Unique request identifier
            method: HTTP method
            url: Target URL
            headers: Request headers
            body_data: Parsed request body
            session_id: Codex session ID
        """
        if not self.verbose_api:
            return

        # Log to console with redacted headers
        logger.info(
            "verbose_codex_request",
            request_id=request_id,
            method=method,
            url=url,
            headers=redact_sensitive_headers(headers),
            session_id=session_id,
            instructions_preview=(
                body_data.get("instructions", "")[:100] + "..."
                if body_data and body_data.get("instructions")
                else None
            ),
        )

        # Save complete request to file (without redaction)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        await write_request_log(
            request_id=request_id,
            log_type="codex_request",
            data={
                "method": method,
                "url": url,
                "headers": dict(headers),
                "body": body_data,
                "session_id": session_id,
            },
            timestamp=timestamp,
        )

    async def log_codex_response(
        self,
        request_id: str,
        status_code: int,
        headers: dict[str, str],
        body_data: dict[str, Any] | None,
    ) -> None:
        """Log complete non-streaming Codex response.

        Args:
            request_id: Unique request identifier
            status_code: HTTP status code
            headers: Response headers
            body_data: Parsed response body
        """
        if not self.verbose_api:
            return

        # Log to console with redacted headers
        logger.info(
            "verbose_codex_response",
            request_id=request_id,
            status_code=status_code,
            headers=redact_sensitive_headers(headers),
            response_type="non_streaming",
        )

        # Save complete response to file
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        await write_request_log(
            request_id=request_id,
            log_type="codex_response",
            data={
                "status_code": status_code,
                "headers": dict(headers),
                "body": body_data,
            },
            timestamp=timestamp,
        )

    async def log_codex_response_headers(
        self,
        request_id: str,
        status_code: int,
        headers: dict[str, str],
        stream_type: str,
    ) -> None:
        """Log streaming Codex response headers.

        Args:
            request_id: Unique request identifier
            status_code: HTTP status code
            headers: Response headers
            stream_type: Type of stream (e.g., "codex_sse")
        """
        if not self.verbose_api:
            return

        # Log to console with redacted headers
        logger.info(
            "verbose_codex_response_headers",
            request_id=request_id,
            status_code=status_code,
            headers=redact_sensitive_headers(headers),
            stream_type=stream_type,
        )

        # Save response headers to file
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        await write_request_log(
            request_id=request_id,
            log_type="codex_response_headers",
            data={
                "status_code": status_code,
                "headers": dict(headers),
                "stream_type": stream_type,
            },
            timestamp=timestamp,
        )

    async def log_codex_streaming_complete(
        self,
        request_id: str,
        chunks: list[bytes],
    ) -> None:
        """Log complete streaming data after stream finishes.

        Args:
            request_id: Unique request identifier
            chunks: List of collected streaming chunks
        """
        if not self.verbose_api:
            return

        # Combine chunks and decode for analysis
        complete_data = b"".join(chunks)
        try:
            decoded_data = complete_data.decode("utf-8", errors="replace")
        except Exception:
            decoded_data = f"<binary data of length {len(complete_data)}>"

        # Log to console with preview
        logger.info(
            "verbose_codex_streaming_complete",
            request_id=request_id,
            total_bytes=len(complete_data),
            chunk_count=len(chunks),
            data_preview=decoded_data[:200] + "..."
            if len(decoded_data) > 200
            else decoded_data,
        )

        # Save complete streaming data to file
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        await write_request_log(
            request_id=request_id,
            log_type="codex_streaming_complete",
            data={
                "total_bytes": len(complete_data),
                "chunk_count": len(chunks),
                "complete_data": decoded_data,
            },
            timestamp=timestamp,
        )

    async def log_stream_response_headers(
        self,
        ctx: "RequestContext",
        status_code: int,
        headers: dict[str, str],
        is_openai: bool,
    ) -> None:
        """Log upstream response headers for streaming.

        Args:
            ctx: Request context
            status_code: HTTP status code
            headers: Response headers
            is_openai: Whether this is an OpenAI format request
        """
        if not self.verbose_api:
            return

        request_id = ctx.request_id
        timestamp = ctx.get_log_timestamp_prefix()
        await write_request_log(
            request_id=request_id,
            log_type="upstream_response_headers",
            data={
                "status_code": status_code,
                "headers": dict(headers),
                "stream_type": "openai_sse" if is_openai else "anthropic_sse",
            },
            timestamp=timestamp,
        )

    async def log_streaming_chunk(
        self,
        ctx: "RequestContext",
        chunk: bytes,
        timestamp: str | None = None,
    ) -> None:
        """Log a streaming chunk to the request log.

        Args:
            ctx: Request context
            chunk: Raw chunk bytes
            timestamp: Optional timestamp (uses context timestamp if not provided)
        """
        request_id = ctx.request_id
        ts = timestamp or ctx.get_log_timestamp_prefix()
        await append_streaming_log(
            request_id=request_id,
            log_type="upstream_streaming",
            data=chunk,
            timestamp=ts,
        )
