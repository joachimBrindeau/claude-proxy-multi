"""Helper utilities for proxy route handlers."""

from collections.abc import AsyncIterator

from fastapi import Request
from fastapi.responses import StreamingResponse

from claude_code_proxy.api.responses import ProxyResponse


def strip_problematic_headers(headers: dict[str, str]) -> dict[str, str]:
    """Strip headers that can cause compression/encoding issues.

    HTTPX (used by both the proxy client and test client) automatically decompresses
    responses. If we forward content-encoding headers from the upstream API,
    the test client will try to decompress already-decompressed data, causing
    "Error -3 while decompressing data: incorrect header check".

    Args:
        headers: Original response headers

    Returns:
        Headers with problematic ones removed

    """
    # Headers to exclude (case-insensitive matching)
    excluded_headers = {
        "content-encoding",  # HTTPX auto-decompresses, forwarding causes double decompression
        "transfer-encoding",  # Chunked encoding is handled by framework
    }

    return {
        key: value
        for key, value in headers.items()
        if key.lower() not in excluded_headers
    }


def extract_request_data(
    request: Request,
) -> tuple[dict[str, str], dict[str, str | list[str]] | None, str]:
    """Extract headers, query params, and service path from request.

    Args:
        request: FastAPI request object

    Returns:
        Tuple of (headers, query_params, service_path)

    """
    headers = dict(request.headers)
    query_params: dict[str, str | list[str]] | None = (
        dict(request.query_params) if request.query_params else None
    )
    service_path = request.url.path.removeprefix("/api")
    return headers, query_params, service_path


def create_error_response(
    status_code: int,
    response_headers: dict[str, str],
    response_body: bytes,
) -> ProxyResponse:
    """Create error response with proper headers.

    Args:
        status_code: HTTP status code
        response_headers: Response headers
        response_body: Response body bytes

    Returns:
        ProxyResponse object

    """
    # Strip problematic headers to prevent compression issues
    clean_headers = strip_problematic_headers(response_headers)

    return ProxyResponse(
        content=response_body,
        status_code=status_code,
        headers=clean_headers,
        media_type=clean_headers.get("content-type", "application/json"),
    )


def create_regular_response(
    status_code: int,
    response_headers: dict[str, str],
    response_body: bytes,
) -> ProxyResponse:
    """Create regular (non-streaming) response with proper headers.

    Args:
        status_code: HTTP status code
        response_headers: Response headers
        response_body: Response body bytes

    Returns:
        ProxyResponse object

    """
    # Strip problematic headers to prevent compression issues
    clean_headers = strip_problematic_headers(response_headers)

    return ProxyResponse(
        content=response_body,
        status_code=status_code,
        headers=clean_headers,
        media_type=clean_headers.get("content-type", "application/json"),
    )


async def create_sse_stream_generator(response_body: bytes) -> AsyncIterator[bytes]:
    """Create SSE stream generator from response body.

    Args:
        response_body: Response body bytes containing SSE data

    Yields:
        Formatted SSE data chunks

    """
    for line in response_body.decode().split("\n"):
        if line.strip():
            yield f"{line}\n".encode()


def prepare_streaming_headers(response_headers: dict[str, str]) -> dict[str, str]:
    """Prepare headers for SSE streaming response.

    Args:
        response_headers: Original response headers

    Returns:
        Headers configured for SSE streaming

    """
    # Strip problematic headers first
    streaming_headers = strip_problematic_headers(response_headers)

    streaming_headers["Cache-Control"] = "no-cache"
    streaming_headers["Connection"] = "keep-alive"

    if "content-type" not in streaming_headers:
        streaming_headers["content-type"] = "text/event-stream"

    return streaming_headers


def create_streaming_response(
    response_headers: dict[str, str],
    response_body: bytes,
) -> StreamingResponse:
    """Create StreamingResponse for SSE data.

    Args:
        response_headers: Response headers
        response_body: Response body bytes containing SSE data

    Returns:
        StreamingResponse configured for SSE

    """
    streaming_headers = prepare_streaming_headers(response_headers)

    return StreamingResponse(
        create_sse_stream_generator(response_body),
        media_type="text/event-stream",
        headers=streaming_headers,
    )


def is_streaming_response(response_headers: dict[str, str]) -> bool:
    """Check if response is SSE streaming based on content-type.

    Args:
        response_headers: Response headers to check

    Returns:
        True if content-type indicates SSE streaming

    """
    content_type = response_headers.get("content-type", "")
    return "text/event-stream" in content_type


def handle_proxy_response(
    status_code: int,
    response_headers: dict[str, str],
    response_body: bytes,
) -> StreamingResponse | ProxyResponse:
    """Handle proxy response based on status code and content type.

    Args:
        status_code: HTTP status code
        response_headers: Response headers
        response_body: Response body bytes

    Returns:
        Appropriate response type (StreamingResponse or ProxyResponse)

    """
    # Handle error responses
    if status_code >= 400:
        return create_error_response(status_code, response_headers, response_body)

    # Handle streaming responses
    if is_streaming_response(response_headers):
        return create_streaming_response(response_headers, response_body)

    # Handle regular responses
    return create_regular_response(status_code, response_headers, response_body)
