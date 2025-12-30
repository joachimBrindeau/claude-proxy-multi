"""Proxy endpoints for CCProxy API Server."""

import asyncio
from collections.abc import AsyncIterator

import httpx
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import StreamingResponse

from ccproxy.api.dependencies import ProxyServiceDep
from ccproxy.api.responses import ProxyResponse
from ccproxy.auth.conditional import ConditionalAuthDep
from ccproxy.exceptions import CCProxyError


# Create the router for proxy endpoints
router = APIRouter(tags=["proxy"])


@router.post("/v1/messages", response_model=None)
async def create_anthropic_message(
    request: Request,
    proxy_service: ProxyServiceDep,
    auth: ConditionalAuthDep,
) -> StreamingResponse | Response:
    """Create a message using Claude AI with Anthropic format.

    This endpoint handles Anthropic API format requests and forwards them
    directly to Claude via the proxy service.
    """
    try:
        # Get request body
        body = await request.body()

        # Get headers and query params
        headers = dict(request.headers)
        query_params: dict[str, str | list[str]] | None = (
            dict(request.query_params) if request.query_params else None
        )

        # Handle the request using proxy service directly
        # Strip the /api prefix from the path
        service_path = request.url.path.removeprefix("/api")
        response = await proxy_service.handle_request(
            method=request.method,
            path=service_path,
            headers=headers,
            body=body,
            query_params=query_params,
            request=request,  # Pass the request object for context access
        )

        # Return appropriate response type
        if isinstance(response, StreamingResponse):
            # Already a streaming response
            return response
        else:
            # Tuple response - handle regular response
            status_code, response_headers, response_body = response

            if status_code >= 400:
                # Forward error response directly with headers
                return ProxyResponse(
                    content=response_body,
                    status_code=status_code,
                    headers=response_headers,
                    media_type=response_headers.get("content-type", "application/json"),
                )

            # Check if this is a streaming response based on content-type
            content_type = response_headers.get("content-type", "")
            if "text/event-stream" in content_type:
                # Return as streaming response
                async def stream_generator() -> AsyncIterator[bytes]:
                    # Split the SSE data into chunks
                    for line in response_body.decode().split("\n"):
                        if line.strip():
                            yield f"{line}\n".encode()

                # Start with the response headers from proxy service
                streaming_headers = response_headers.copy()

                # Ensure critical headers for streaming
                streaming_headers["Cache-Control"] = "no-cache"
                streaming_headers["Connection"] = "keep-alive"

                # Set content-type if not already set by upstream
                if "content-type" not in streaming_headers:
                    streaming_headers["content-type"] = "text/event-stream"

                return StreamingResponse(
                    stream_generator(),
                    media_type="text/event-stream",
                    headers=streaming_headers,
                )
            else:
                # Return response with headers
                return ProxyResponse(
                    content=response_body,  # Use original body to preserve exact format
                    status_code=status_code,
                    headers=response_headers,
                    media_type=response_headers.get("content-type", "application/json"),
                )

    except (HTTPException, CCProxyError):
        # Re-raise HTTP and proxy errors to be handled by error middleware
        raise
    except asyncio.CancelledError:
        # Streaming was cancelled by client disconnect
        raise
    except (httpx.HTTPError, httpx.ConnectError) as e:
        # HTTP client errors during proxy request
        raise HTTPException(
            status_code=502, detail=f"Upstream service error: {str(e)}"
        ) from e
    except (KeyError, TypeError, ValueError) as e:
        # Data transformation or format errors during request/response processing
        raise HTTPException(
            status_code=500, detail=f"Internal server error: {str(e)}"
        ) from e


@router.post("/v1/chat/completions", response_model=None)
async def create_openai_chat_completion(
    request: Request,
    proxy_service: ProxyServiceDep,
    auth: ConditionalAuthDep,
) -> StreamingResponse | Response:
    """Create a chat completion using Claude AI with OpenAI format.

    This endpoint handles OpenAI Chat Completions API format requests and
    translates them for Claude via the proxy service.
    """
    try:
        # Get request body
        body = await request.body()

        # Get headers and query params
        headers = dict(request.headers)
        query_params: dict[str, str | list[str]] | None = (
            dict(request.query_params) if request.query_params else None
        )

        # Handle the request using proxy service directly
        # Strip the /api prefix from the path
        service_path = request.url.path.removeprefix("/api")
        response = await proxy_service.handle_request(
            method=request.method,
            path=service_path,
            headers=headers,
            body=body,
            query_params=query_params,
            request=request,  # Pass the request object for context access
        )

        # Return appropriate response type
        if isinstance(response, StreamingResponse):
            # Already a streaming response
            return response
        else:
            # Tuple response - handle regular response
            status_code, response_headers, response_body = response

            if status_code >= 400:
                # Forward error response directly with headers
                return ProxyResponse(
                    content=response_body,
                    status_code=status_code,
                    headers=response_headers,
                    media_type=response_headers.get("content-type", "application/json"),
                )

            # Check if this is a streaming response based on content-type
            content_type = response_headers.get("content-type", "")
            if "text/event-stream" in content_type:
                # Return as streaming response
                async def stream_generator() -> AsyncIterator[bytes]:
                    # Split the SSE data into chunks
                    for line in response_body.decode().split("\n"):
                        if line.strip():
                            yield f"{line}\n".encode()

                # Start with the response headers from proxy service
                streaming_headers = response_headers.copy()

                # Ensure critical headers for streaming
                streaming_headers["Cache-Control"] = "no-cache"
                streaming_headers["Connection"] = "keep-alive"

                # Set content-type if not already set by upstream
                if "content-type" not in streaming_headers:
                    streaming_headers["content-type"] = "text/event-stream"

                return StreamingResponse(
                    stream_generator(),
                    media_type="text/event-stream",
                    headers=streaming_headers,
                )
            else:
                # Return response with headers
                return ProxyResponse(
                    content=response_body,  # Use original body to preserve exact format
                    status_code=status_code,
                    headers=response_headers,
                    media_type=response_headers.get("content-type", "application/json"),
                )

    except (HTTPException, CCProxyError):
        # Re-raise HTTP and proxy errors to be handled by error middleware
        raise
    except asyncio.CancelledError:
        # Streaming was cancelled by client disconnect
        raise
    except (httpx.HTTPError, httpx.ConnectError) as e:
        # HTTP client errors during proxy request
        raise HTTPException(
            status_code=502, detail=f"Upstream service error: {str(e)}"
        ) from e
    except (KeyError, TypeError, ValueError) as e:
        # Data transformation or format errors during request/response processing
        raise HTTPException(
            status_code=500, detail=f"Internal server error: {str(e)}"
        ) from e
