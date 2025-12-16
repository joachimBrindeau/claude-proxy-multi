"""Codex request handler for OpenAI Codex proxy.

This module handles OpenAI Codex-specific proxy requests including
streaming and non-streaming responses with proper request/response transformation.
"""

import json
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING, Any
from uuid import uuid4

import httpx
import jwt
import structlog
from fastapi import Request
from fastapi.responses import StreamingResponse
from starlette.responses import Response

if TYPE_CHECKING:
    from ccproxy.config.settings import Settings
    from ccproxy.core.codex_transformers import CodexRequestTransformer
    from ccproxy.services.verbose_logger import VerboseLogger

logger = structlog.get_logger(__name__)


class CodexHandler:
    """Handles OpenAI Codex proxy requests.

    Processes Codex requests with proper streaming/non-streaming handling,
    request transformation, and response logging.
    """

    def __init__(
        self,
        codex_transformer: "CodexRequestTransformer",
        verbose_logger: "VerboseLogger",
        app_state: Any = None,
    ) -> None:
        """Initialize the Codex handler.

        Args:
            codex_transformer: Transformer for Codex requests
            verbose_logger: Logger for verbose output
            app_state: FastAPI app state for accessing detection data
        """
        self.codex_transformer = codex_transformer
        self.verbose_logger = verbose_logger
        self.app_state = app_state

    async def handle(
        self,
        method: str,
        path: str,
        session_id: str,
        access_token: str,
        request: Request,
        settings: "Settings",
    ) -> StreamingResponse | Response:
        """Handle OpenAI Codex proxy request with request/response capture.

        Args:
            method: HTTP method
            path: Request path (e.g., "/responses" or "/{session_id}/responses")
            session_id: Resolved session ID
            access_token: OpenAI access token
            request: FastAPI request object
            settings: Application settings

        Returns:
            StreamingResponse or regular Response
        """
        try:
            # Read request body - check if already stored by middleware
            if hasattr(request.state, "body"):
                body = request.state.body
            else:
                body = await request.body()

            # Parse request data to capture the instructions field and other metadata
            request_data = self._parse_request_body(body)

            # Extract account_id from token
            account_id = self._extract_account_id(access_token)

            # Get Codex detection data from app state
            codex_detection_data = None
            if self.app_state and hasattr(self.app_state, "codex_detection_data"):
                codex_detection_data = self.app_state.codex_detection_data

            # Use CodexRequestTransformer to build request
            original_headers = dict(request.headers)
            transformed_request = await self.codex_transformer.transform_codex_request(
                method=method,
                path=path,
                headers=original_headers,
                body=body,
                access_token=access_token,
                session_id=session_id,
                account_id=account_id,
                codex_detection_data=codex_detection_data,
                target_base_url=settings.codex.base_url,
            )

            target_url = transformed_request["url"]
            headers = transformed_request["headers"]
            transformed_body = transformed_request["body"] or body

            # Parse transformed body for logging
            transformed_request_data = request_data
            if transformed_body and transformed_body != body:
                try:
                    transformed_request_data = json.loads(
                        transformed_body.decode("utf-8")
                    )
                except (json.JSONDecodeError, UnicodeDecodeError):
                    transformed_request_data = request_data

            # Generate request ID for logging
            request_id = f"codex_{uuid4().hex[:8]}"

            # Log Codex request (including instructions field and headers)
            await self.verbose_logger.log_codex_request(
                request_id=request_id,
                method=method,
                url=target_url,
                headers=headers,
                body_data=transformed_request_data,
                session_id=session_id,
            )

            # Check if user explicitly requested streaming (from original request)
            user_requested_streaming = self.codex_transformer._is_streaming_request(
                body
            )

            # Forward request to ChatGPT backend
            if user_requested_streaming:
                return await self._handle_streaming_request(
                    method=method,
                    target_url=target_url,
                    headers=headers,
                    transformed_body=transformed_body,
                    request_id=request_id,
                    session_id=session_id,
                )
            else:
                return await self._handle_non_streaming_request(
                    method=method,
                    target_url=target_url,
                    headers=headers,
                    transformed_body=transformed_body,
                    request_id=request_id,
                )

        except Exception as e:
            logger.error("Codex request failed", error=str(e), session_id=session_id)
            raise

    def _parse_request_body(self, body: bytes | None) -> dict[str, Any]:
        """Parse request body to extract metadata.

        Args:
            body: Request body bytes

        Returns:
            Parsed request data dict
        """
        if not body:
            return {}

        try:
            return json.loads(body.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            logger.warning(
                "codex_json_decode_failed",
                error=str(e),
                body_preview=body[:100].decode("utf-8", errors="replace")
                if body
                else None,
                body_length=len(body) if body else 0,
            )
            return {}

    def _extract_account_id(self, access_token: str) -> str:
        """Extract account_id from JWT token.

        Args:
            access_token: JWT access token

        Returns:
            Account ID or "unknown"
        """
        try:
            decoded = jwt.decode(access_token, options={"verify_signature": False})
            return decoded.get(
                "org_id", decoded.get("sub", decoded.get("account_id", "unknown"))
            )
        except Exception:
            return "unknown"

    async def _handle_streaming_request(
        self,
        method: str,
        target_url: str,
        headers: dict[str, str],
        transformed_body: bytes,
        request_id: str,
        session_id: str,
    ) -> StreamingResponse | Response:
        """Handle streaming Codex request.

        Args:
            method: HTTP method
            target_url: Target URL
            headers: Request headers
            transformed_body: Transformed request body
            request_id: Request ID for logging
            session_id: Codex session ID

        Returns:
            StreamingResponse or error Response
        """
        collected_chunks: list[bytes] = []
        chunk_count = 0
        total_bytes = 0
        response_status_code = 200
        response_headers: dict[str, str] = {}

        async def stream_codex_response() -> AsyncGenerator[bytes, None]:
            nonlocal collected_chunks, chunk_count, total_bytes
            nonlocal response_status_code, response_headers

            logger.debug(
                "proxy_service_streaming_started",
                request_id=request_id,
                session_id=session_id,
            )

            async with (
                httpx.AsyncClient(timeout=240.0) as client,
                client.stream(
                    method=method,
                    url=target_url,
                    headers=headers,
                    content=transformed_body,
                ) as response,
            ):
                # Capture response info for error checking
                response_status_code = response.status_code
                response_headers = dict(response.headers)

                # Log response headers for streaming
                await self.verbose_logger.log_codex_response_headers(
                    request_id=request_id,
                    status_code=response.status_code,
                    headers=dict(response.headers),
                    stream_type="codex_sse",
                )

                # Check if upstream actually returned streaming
                content_type = response.headers.get("content-type", "")
                is_streaming = "text/event-stream" in content_type

                if not is_streaming:
                    logger.warning(
                        "codex_expected_streaming_but_got_regular",
                        content_type=content_type,
                        status_code=response.status_code,
                    )

                async for chunk in response.aiter_bytes():
                    chunk_count += 1
                    chunk_size = len(chunk)
                    total_bytes += chunk_size
                    collected_chunks.append(chunk)

                    logger.debug(
                        "proxy_service_streaming_chunk",
                        request_id=request_id,
                        chunk_number=chunk_count,
                        chunk_size=chunk_size,
                        total_bytes=total_bytes,
                    )

                    yield chunk

            logger.debug(
                "proxy_service_streaming_complete",
                request_id=request_id,
                total_chunks=chunk_count,
                total_bytes=total_bytes,
            )

            # Log the complete stream data after streaming finishes
            await self.verbose_logger.log_codex_streaming_complete(
                request_id=request_id,
                chunks=collected_chunks,
            )

        # Execute the stream generator to collect the response
        generator_chunks = []
        async for chunk in stream_codex_response():
            generator_chunks.append(chunk)

        # Now check if this should be an error response
        content_type = response_headers.get("content-type", "")
        if response_status_code >= 400 and "text/event-stream" not in content_type:
            # Return error as regular Response with proper status code
            error_content = b"".join(collected_chunks)
            logger.warning(
                "codex_returning_error_as_regular_response",
                status_code=response_status_code,
                content_type=content_type,
                content_preview=error_content[:200].decode("utf-8", errors="replace"),
            )
            return Response(
                content=error_content,
                status_code=response_status_code,
                headers=response_headers,
            )

        # Return normal streaming response
        async def replay_stream() -> AsyncGenerator[bytes, None]:
            for chunk in generator_chunks:
                yield chunk

        # Forward upstream headers but filter out incompatible ones for streaming
        streaming_headers = dict(response_headers)
        # Remove headers that conflict with streaming responses
        streaming_headers.pop("content-length", None)
        streaming_headers.pop("content-encoding", None)
        streaming_headers.pop("date", None)
        # Set streaming-specific headers
        streaming_headers.update(
            {
                "content-type": "text/event-stream",
                "cache-control": "no-cache",
                "connection": "keep-alive",
            }
        )

        return StreamingResponse(
            replay_stream(),
            media_type="text/event-stream",
            headers=streaming_headers,
        )

    async def _handle_non_streaming_request(
        self,
        method: str,
        target_url: str,
        headers: dict[str, str],
        transformed_body: bytes,
        request_id: str,
    ) -> Response:
        """Handle non-streaming Codex request.

        Args:
            method: HTTP method
            target_url: Target URL
            headers: Request headers
            transformed_body: Transformed request body
            request_id: Request ID for logging

        Returns:
            Response object
        """
        async with httpx.AsyncClient(timeout=240.0) as client:
            response = await client.request(
                method=method,
                url=target_url,
                headers=headers,
                content=transformed_body,
            )

            # Check if upstream response is streaming (shouldn't happen)
            content_type = response.headers.get("content-type", "")
            transfer_encoding = response.headers.get("transfer-encoding", "")
            upstream_is_streaming = "text/event-stream" in content_type or (
                transfer_encoding == "chunked" and content_type == ""
            )

            logger.debug(
                "codex_response_non_streaming",
                content_type=content_type,
                upstream_is_streaming=upstream_is_streaming,
                transfer_encoding=transfer_encoding,
            )

            if upstream_is_streaming:
                return await self._convert_stream_to_json(
                    response, request_id
                )
            else:
                return await self._handle_regular_response(
                    response, request_id
                )

    async def _convert_stream_to_json(
        self,
        response: httpx.Response,
        request_id: str,
    ) -> Response:
        """Convert streaming response to JSON.

        Args:
            response: Upstream response
            request_id: Request ID for logging

        Returns:
            JSON Response
        """
        logger.debug("converting_upstream_stream_to_json", request_id=request_id)

        collected_chunks = []
        async for chunk in response.aiter_bytes():
            collected_chunks.append(chunk)

        # Combine all chunks
        full_content = b"".join(collected_chunks)

        # Try to parse the streaming data and extract the final response
        response_content = self._parse_streaming_to_json(full_content)

        # Log the complete response
        try:
            response_data = json.loads(response_content.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            response_data = {
                "raw_content": response_content.decode("utf-8", errors="replace")
            }

        await self.verbose_logger.log_codex_response(
            request_id=request_id,
            status_code=response.status_code,
            headers=dict(response.headers),
            body_data=response_data,
        )

        # Return as JSON response
        return Response(
            content=response_content,
            status_code=response.status_code,
            headers={
                "content-type": "application/json",
                "content-length": str(len(response_content)),
            },
            media_type="application/json",
        )

    def _parse_streaming_to_json(self, full_content: bytes) -> bytes:
        """Parse streaming SSE data to extract JSON response.

        Args:
            full_content: Combined streaming content

        Returns:
            JSON response bytes
        """
        try:
            content_str = full_content.decode("utf-8")
            lines = content_str.strip().split("\n")

            # Look for the last data line with JSON content
            final_json = None
            for line in reversed(lines):
                if line.startswith("data: ") and not line.endswith("[DONE]"):
                    try:
                        json_str = line[6:]  # Remove "data: " prefix
                        final_json = json.loads(json_str)
                        break
                    except json.JSONDecodeError:
                        continue

            if final_json:
                return json.dumps(final_json).encode("utf-8")
            else:
                # Fallback: return the raw content
                return full_content

        except (UnicodeDecodeError, json.JSONDecodeError):
            # Fallback: return raw content
            return full_content

    async def _handle_regular_response(
        self,
        response: httpx.Response,
        request_id: str,
    ) -> Response:
        """Handle regular non-streaming response.

        Args:
            response: Upstream response
            request_id: Request ID for logging

        Returns:
            Response object
        """
        # Parse response for logging
        response_data = None
        try:
            response_data = (
                json.loads(response.content.decode("utf-8"))
                if response.content
                else {}
            )
        except (json.JSONDecodeError, UnicodeDecodeError):
            response_data = {
                "raw_content": response.content.decode("utf-8", errors="replace")
            }

        await self.verbose_logger.log_codex_response(
            request_id=request_id,
            status_code=response.status_code,
            headers=dict(response.headers),
            body_data=response_data,
        )

        # Return regular response
        return Response(
            content=response.content,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.headers.get("content-type"),
        )
