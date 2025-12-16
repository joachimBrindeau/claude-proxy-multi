"""Proxy service for orchestrating Claude API requests with business logic."""

import json
import os
import time
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import TYPE_CHECKING, Any

import structlog
from fastapi import HTTPException, Request
from fastapi.responses import StreamingResponse
from starlette.responses import Response
from typing_extensions import TypedDict

from ccproxy.config.settings import Settings
from ccproxy.core.codex_transformers import CodexRequestTransformer
from ccproxy.core.http import BaseProxyClient
from ccproxy.core.http_transformers import (
    HTTPRequestTransformer,
    HTTPResponseTransformer,
)
from ccproxy.observability import (
    PrometheusMetrics,
    get_metrics,
    request_context,
    timed_operation,
)
from ccproxy.services.bypass_generator import BypassGenerator
from ccproxy.services.codex_handler import CodexHandler
from ccproxy.services.credentials.manager import CredentialsManager
from ccproxy.services.request_metadata import (
    extract_message_type,
    extract_metadata,
    is_streaming_request,
)
from ccproxy.services.streaming_handler import StreamingHandler
from ccproxy.services.token_provider import TokenProvider
from ccproxy.services.verbose_logger import VerboseLogger
from ccproxy.testing import RealisticMockResponseGenerator


if TYPE_CHECKING:
    from ccproxy.observability.context import RequestContext


class RequestData(TypedDict):
    """Typed structure for transformed request data."""

    method: str
    url: str
    headers: dict[str, str]
    body: bytes | None


class ResponseData(TypedDict):
    """Typed structure for transformed response data."""

    status_code: int
    headers: dict[str, str]
    body: bytes


logger = structlog.get_logger(__name__)


class ProxyService:
    """Claude-specific proxy orchestration with business logic.

    This service orchestrates the complete proxy flow including:
    - Authentication management
    - Request/response transformations
    - Metrics collection (future)
    - Error handling and logging

    Pure HTTP forwarding is delegated to BaseProxyClient.
    """

    def __init__(
        self,
        proxy_client: BaseProxyClient,
        credentials_manager: CredentialsManager,
        settings: Settings,
        proxy_mode: str = "full",
        target_base_url: str = "https://api.anthropic.com",
        metrics: PrometheusMetrics | None = None,
        app_state: Any = None,
    ) -> None:
        """Initialize the proxy service.

        Args:
            proxy_client: HTTP client for pure forwarding
            credentials_manager: Authentication manager
            settings: Application settings
            proxy_mode: Transformation mode - "minimal" or "full"
            target_base_url: Base URL for the target API
            metrics: Prometheus metrics collector (optional)
            app_state: FastAPI app state for accessing detection data
        """
        self.proxy_client = proxy_client
        self.credentials_manager = credentials_manager
        self.settings = settings
        self.proxy_mode = proxy_mode
        self.target_base_url = target_base_url.rstrip("/")
        self.metrics = metrics or get_metrics()
        self.app_state = app_state

        # Create concrete transformers
        self.request_transformer = HTTPRequestTransformer()
        self.response_transformer = HTTPResponseTransformer()
        self.codex_transformer = CodexRequestTransformer()

        # Create OpenAI adapter for stream transformation
        from ccproxy.adapters.openai.adapter import OpenAIAdapter

        self.openai_adapter = OpenAIAdapter()

        # Create mock response generator for bypass mode
        self.mock_generator = RealisticMockResponseGenerator()

        # Cache environment-based configuration
        self._proxy_url = self._init_proxy_url()
        self._ssl_context = self._init_ssl_context()

        # Initialize verbose logger
        verbose_streaming = (
            os.environ.get("CCPROXY_VERBOSE_STREAMING", "false").lower() == "true"
        )
        verbose_api = (
            os.environ.get("CCPROXY_VERBOSE_API", "false").lower() == "true"
        )
        self.verbose_logger = VerboseLogger(
            verbose_api=verbose_api,
            verbose_streaming=verbose_streaming,
        )

        # Initialize token provider
        self.token_provider = TokenProvider(credentials_manager=credentials_manager)

        # Initialize bypass generator for mock responses
        self.bypass = BypassGenerator(
            mock_generator=self.mock_generator,
            openai_adapter=self.openai_adapter,
            metrics=self.metrics,
        )

        # Initialize streaming handler
        self.streaming = StreamingHandler(
            response_transformer=self.response_transformer,
            openai_adapter=self.openai_adapter,
            verbose_logger=self.verbose_logger,
            metrics=self.metrics,
            proxy_url=self._proxy_url,
            ssl_context=self._ssl_context,
            proxy_mode=self.proxy_mode,
        )

        # Initialize Codex handler
        self.codex = CodexHandler(
            codex_transformer=self.codex_transformer,
            verbose_logger=self.verbose_logger,
            app_state=self.app_state,
        )

    def _init_proxy_url(self) -> str | None:
        """Initialize proxy URL from environment variables."""
        # Check for standard proxy environment variables
        # For HTTPS requests, prioritize HTTPS_PROXY
        https_proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
        all_proxy = os.environ.get("ALL_PROXY")
        http_proxy = os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy")

        proxy_url = https_proxy or all_proxy or http_proxy

        if proxy_url:
            logger.debug("proxy_configured", proxy_url=proxy_url)

        return proxy_url

    def _init_ssl_context(self) -> str | bool:
        """Initialize SSL context configuration from environment variables."""
        # Check for custom CA bundle
        ca_bundle = os.environ.get("REQUESTS_CA_BUNDLE") or os.environ.get(
            "SSL_CERT_FILE"
        )

        # Check if SSL verification should be disabled (NOT RECOMMENDED)
        ssl_verify = os.environ.get("SSL_VERIFY", "true").lower()

        if ca_bundle and Path(ca_bundle).exists():
            logger.info("ca_bundle_configured", ca_bundle=ca_bundle)
            return ca_bundle
        elif ssl_verify in ("false", "0", "no"):
            logger.warning("ssl_verification_disabled")
            return False
        else:
            logger.debug("ssl_verification_default")
            return True

    async def handle_request(
        self,
        method: str,
        path: str,
        headers: dict[str, str],
        body: bytes | None = None,
        query_params: dict[str, str | list[str]] | None = None,
        timeout: float = 240.0,
        request: Request | None = None,  # Optional FastAPI Request object
    ) -> tuple[int, dict[str, str], bytes] | StreamingResponse:
        """Handle a proxy request with full business logic orchestration.

        Args:
            method: HTTP method
            path: Request path (without /unclaude prefix)
            headers: Request headers
            body: Request body
            query_params: Query parameters
            timeout: Request timeout in seconds
            request: Optional FastAPI Request object for accessing request context

        Returns:
            Tuple of (status_code, headers, body) or StreamingResponse for streaming

        Raises:
            HTTPException: If request fails
        """
        # Extract request metadata
        model, streaming = extract_metadata(body)
        endpoint = path.split("/")[-1] if path else "unknown"

        # Use existing context from request if available, otherwise create new one
        if request and hasattr(request, "state") and hasattr(request.state, "context"):
            # Use existing context from middleware
            ctx = request.state.context
            # Add service-specific metadata
            ctx.add_metadata(
                endpoint=endpoint,
                model=model,
                streaming=streaming,
                service_type="proxy_service",
            )
            # Create a context manager that preserves the existing context's lifecycle
            # This ensures __aexit__ is called for proper access logging
            from contextlib import asynccontextmanager

            @asynccontextmanager
            async def existing_context_manager() -> AsyncGenerator[Any, None]:
                try:
                    yield ctx
                finally:
                    # Let the existing context handle its own lifecycle
                    # The middleware or parent context will call __aexit__
                    pass

            context_manager: Any = existing_context_manager()
        else:
            # Create new context for observability
            context_manager = request_context(
                method=method,
                path=path,
                endpoint=endpoint,
                model=model,
                streaming=streaming,
                service_type="proxy_service",
                metrics=self.metrics,
            )

        async with context_manager as ctx:
            try:
                # 1. Authentication - get access token
                async with timed_operation("oauth_token", ctx.request_id):
                    logger.debug("oauth_token_retrieval_start")
                    access_token = await self.token_provider.get_token(request)

                # 2. Request transformation
                async with timed_operation("request_transform", ctx.request_id):
                    injection_mode = (
                        self.settings.claude.system_prompt_injection_mode.value
                    )
                    logger.debug(
                        "request_transform_start",
                        system_prompt_injection_mode=injection_mode,
                    )
                    transformed_request = (
                        await self.request_transformer.transform_proxy_request(
                            method,
                            path,
                            headers,
                            body,
                            query_params,
                            access_token,
                            self.target_base_url,
                            self.app_state,
                            injection_mode,
                        )
                    )

                # 3. Check for bypass header to skip upstream forwarding
                bypass_upstream = (
                    headers.get("X-CCProxy-Bypass-Upstream", "").lower() == "true"
                )

                if bypass_upstream:
                    logger.debug("bypassing_upstream_forwarding_due_to_header")
                    # Determine message type from request body for realistic response generation
                    message_type = extract_message_type(body)

                    # Check if this will be a streaming response
                    should_stream = streaming or is_streaming_request(
                        transformed_request["headers"]
                    )

                    # Determine response format based on original request path
                    is_openai_format = self.response_transformer._is_openai_request(
                        path
                    )

                    if should_stream:
                        return await self.bypass.generate_streaming(
                            model, is_openai_format, ctx, message_type
                        )
                    else:
                        return await self.bypass.generate_standard(
                            model, is_openai_format, ctx, message_type
                        )

                # 3. Forward request using proxy client
                logger.debug("request_forwarding_start", url=transformed_request["url"])

                # Check if this will be a streaming response
                should_stream = streaming or is_streaming_request(
                    transformed_request["headers"]
                )

                if should_stream:
                    logger.debug("streaming_response_detected")
                    return await self.streaming.handle(
                        transformed_request, path, timeout, ctx
                    )
                else:
                    logger.debug("non_streaming_response_detected")

                # Log the outgoing request if verbose API logging is enabled
                await self.verbose_logger.log_api_request(transformed_request, ctx)

                # Handle regular request
                async with timed_operation("api_call", ctx.request_id) as api_op:
                    start_time = time.perf_counter()

                    (
                        status_code,
                        response_headers,
                        response_body,
                    ) = await self.proxy_client.forward(
                        method=transformed_request["method"],
                        url=transformed_request["url"],
                        headers=transformed_request["headers"],
                        body=transformed_request["body"],
                        timeout=timeout,
                    )

                    end_time = time.perf_counter()
                    api_duration = end_time - start_time
                    api_op["duration_seconds"] = api_duration

                # Log the received response if verbose API logging is enabled
                await self.verbose_logger.log_api_response(
                    status_code, response_headers, response_body, ctx
                )

                # 4. Response transformation
                async with timed_operation("response_transform", ctx.request_id):
                    logger.debug("response_transform_start")
                    # For error responses, transform to OpenAI format if needed
                    transformed_response: ResponseData
                    if status_code >= 400:
                        logger.info(
                            "upstream_error_received",
                            status_code=status_code,
                            has_body=bool(response_body),
                            content_length=len(response_body) if response_body else 0,
                        )

                        # Use transformer to handle error transformation (including OpenAI format)
                        transformed_response = (
                            await self.response_transformer.transform_proxy_response(
                                status_code,
                                response_headers,
                                response_body,
                                path,
                                self.proxy_mode,
                            )
                        )
                    else:
                        transformed_response = (
                            await self.response_transformer.transform_proxy_response(
                                status_code,
                                response_headers,
                                response_body,
                                path,
                                self.proxy_mode,
                            )
                        )

                # 5. Extract response metrics using direct JSON parsing
                tokens_input = tokens_output = cache_read_tokens = (
                    cache_write_tokens
                ) = cost_usd = None
                if transformed_response["body"]:
                    try:
                        response_data = json.loads(
                            transformed_response["body"].decode("utf-8")
                        )
                        usage = response_data.get("usage", {})
                        tokens_input = usage.get("input_tokens")
                        tokens_output = usage.get("output_tokens")
                        cache_read_tokens = usage.get("cache_read_input_tokens")
                        cache_write_tokens = usage.get("cache_creation_input_tokens")

                        # Calculate cost including cache tokens if we have tokens and model
                        from ccproxy.utils.cost_calculator import calculate_token_cost

                        cost_usd = calculate_token_cost(
                            tokens_input,
                            tokens_output,
                            model,
                            cache_read_tokens,
                            cache_write_tokens,
                        )
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        pass  # Keep all values as None if parsing fails

                # 6. Update context with response data
                ctx.add_metadata(
                    status_code=status_code,
                    tokens_input=tokens_input,
                    tokens_output=tokens_output,
                    cache_read_tokens=cache_read_tokens,
                    cache_write_tokens=cache_write_tokens,
                    cost_usd=cost_usd,
                )

                return (
                    transformed_response["status_code"],
                    transformed_response["headers"],
                    transformed_response["body"],
                )

            except Exception as e:
                ctx.add_metadata(error=e)
                raise

    async def handle_codex_request(
        self,
        method: str,
        path: str,
        session_id: str,
        access_token: str,
        request: Request,
        settings: Settings,
    ) -> StreamingResponse | Response:
        """Handle OpenAI Codex proxy request.

        Delegates to CodexHandler for processing.

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
        return await self.codex.handle(
            method=method,
            path=path,
            session_id=session_id,
            access_token=access_token,
            request=request,
            settings=settings,
        )

    async def close(self) -> None:
        """Close any resources held by the proxy service."""
        if self.proxy_client:
            await self.proxy_client.close()
        if self.credentials_manager:
            await self.credentials_manager.__aexit__(None, None, None)
