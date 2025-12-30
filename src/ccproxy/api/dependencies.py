"""Shared dependencies for CCProxy API Server."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request
from structlog import get_logger

from ccproxy.config.settings import Settings, get_settings
from ccproxy.core.http import BaseProxyClient
from ccproxy.services.claude_sdk_service import ClaudeSDKService
from ccproxy.services.credentials.manager import CredentialsManager
from ccproxy.services.proxy_service import ProxyService


logger = get_logger(__name__)


def get_cached_settings(request: Request) -> Settings:
    """Get cached settings from app state.

    This avoids recomputing settings on every request by using the
    settings instance computed during application startup.

    Args:
        request: FastAPI request object

    Returns:
        Settings instance from app state

    Raises:
        RuntimeError: If settings are not available in app state
    """
    settings = getattr(request.app.state, "settings", None)
    if settings is None:
        # Fallback to get_settings() for safety, but this should not happen
        # in normal operation after lifespan startup
        logger.warning(
            "Settings not found in app state, falling back to get_settings()"
        )
        settings = get_settings()
    return settings


def get_cached_claude_service(request: Request) -> ClaudeSDKService:
    """Get cached ClaudeSDKService from app state.

    This avoids recreating the ClaudeSDKService on every request by using the
    service instance created during application startup.

    Args:
        request: FastAPI request object

    Returns:
        ClaudeSDKService instance from app state

    Raises:
        RuntimeError: If ClaudeSDKService is not available in app state
    """
    claude_service = getattr(request.app.state, "claude_service", None)
    if claude_service is None:
        # Fallback to get_claude_service() for safety, but this should not happen
        # in normal operation after lifespan startup
        logger.warning(
            "ClaudeSDKService not found in app state, falling back to get_claude_service()"
        )
        # Get dependencies manually for fallback
        settings = get_cached_settings(request)

        claude_service = get_claude_service(settings)
    return claude_service


# Type aliases for dependency injection
SettingsDep = Annotated[Settings, Depends(get_cached_settings)]


def get_claude_service(
    settings: SettingsDep,
) -> ClaudeSDKService:
    """Get Claude SDK service instance.

    Args:
        settings: Application settings dependency

    Returns:
        Claude SDK service instance
    """
    logger.debug("Creating Claude SDK service instance")

    # Check if pooling should be enabled from configuration
    use_pool = settings.claude.sdk_session_pool.enabled
    session_manager = None

    if use_pool:
        logger.info(
            "claude_sdk_pool_enabled",
            message="Using Claude SDK client pooling for improved performance",
            pool_size=settings.claude.sdk_session_pool.max_sessions,
            max_pool_size=settings.claude.sdk_session_pool.max_sessions,
        )
        # Note: Session manager should be created in the lifespan function, not here
        # This dependency function should not create stateful resources

    return ClaudeSDKService(
        settings=settings,
        session_manager=session_manager,
    )


def get_credentials_manager(
    settings: SettingsDep,
) -> CredentialsManager:
    """Get credentials manager instance.

    Args:
        settings: Application settings dependency

    Returns:
        Credentials manager instance
    """
    logger.debug("Creating credentials manager instance")
    return CredentialsManager(config=settings.auth)


def get_proxy_service(
    request: Request,
    settings: SettingsDep,
    credentials_manager: Annotated[
        CredentialsManager, Depends(get_credentials_manager)
    ],
) -> ProxyService:
    """Get proxy service instance.

    Args:
        request: FastAPI request object (for app state access)
        settings: Application settings dependency
        credentials_manager: Credentials manager dependency

    Returns:
        Proxy service instance
    """
    logger.debug("get_proxy_service")
    # Create HTTP client for proxy
    from ccproxy.core.http import HTTPXClient

    http_client = HTTPXClient()
    proxy_client = BaseProxyClient(http_client)

    return ProxyService(
        proxy_client=proxy_client,
        credentials_manager=credentials_manager,
        settings=settings,
        proxy_mode="full",
        target_base_url=settings.reverse_proxy.target_url,
        app_state=request.app.state,  # Pass app state for detection data access
    )


# Type aliases for service dependencies
ClaudeServiceDep = Annotated[ClaudeSDKService, Depends(get_cached_claude_service)]
ProxyServiceDep = Annotated[ProxyService, Depends(get_proxy_service)]
