"""Proxy endpoints for CCProxy API Server."""

import asyncio

import httpx
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import StreamingResponse

from claude_code_proxy.api.dependencies import ProxyServiceDep
from claude_code_proxy.api.routes.helpers import (
    extract_request_data,
    handle_proxy_response,
)
from claude_code_proxy.auth.conditional import ConditionalAuthDep
from claude_code_proxy.exceptions import CCProxyError


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
        body = await request.body()
        headers, query_params, service_path = extract_request_data(request)

        response = await proxy_service.handle_request(
            method=request.method,
            path=service_path,
            headers=headers,
            body=body,
            query_params=query_params,
            request=request,
        )

        # Return streaming response as-is
        if isinstance(response, StreamingResponse):
            return response

        # Handle tuple response
        status_code, response_headers, response_body = response
        return handle_proxy_response(status_code, response_headers, response_body)

    except (HTTPException, CCProxyError):
        raise
    except asyncio.CancelledError:
        raise
    except (httpx.HTTPError, httpx.ConnectError) as e:
        raise HTTPException(
            status_code=502, detail=f"Upstream service error: {str(e)}"
        ) from e
    except (KeyError, TypeError, ValueError) as e:
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
        body = await request.body()
        headers, query_params, service_path = extract_request_data(request)

        response = await proxy_service.handle_request(
            method=request.method,
            path=service_path,
            headers=headers,
            body=body,
            query_params=query_params,
            request=request,
        )

        # Return streaming response as-is
        if isinstance(response, StreamingResponse):
            return response

        # Handle tuple response
        status_code, response_headers, response_body = response
        return handle_proxy_response(status_code, response_headers, response_body)

    except (HTTPException, CCProxyError):
        raise
    except asyncio.CancelledError:
        raise
    except (httpx.HTTPError, httpx.ConnectError) as e:
        raise HTTPException(
            status_code=502, detail=f"Upstream service error: {str(e)}"
        ) from e
    except (KeyError, TypeError, ValueError) as e:
        raise HTTPException(
            status_code=500, detail=f"Internal server error: {str(e)}"
        ) from e
