"""FastAPI application factory for CCProxy API Server."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import APIRouter, FastAPI
from structlog import get_logger

from claude_code_proxy import __version__
from claude_code_proxy.api.lifecycle import (
    LifecycleComponent,
    ShutdownComponent,
    execute_shutdown_sequence,
    execute_startup_sequence,
    log_claude_cli_config,
    log_server_start,
)
from claude_code_proxy.api.middleware.api_key_auth import APIKeyAuthMiddleware
from claude_code_proxy.api.middleware.cors import setup_cors_middleware
from claude_code_proxy.api.middleware.errors import setup_error_handlers
from claude_code_proxy.api.middleware.logging import AccessLogMiddleware
from claude_code_proxy.api.middleware.request_content_logging import (
    RequestContentLoggingMiddleware,
)
from claude_code_proxy.api.middleware.request_id import RequestIDMiddleware
from claude_code_proxy.api.middleware.server_header import ServerHeaderMiddleware
from claude_code_proxy.api.routes.accounts import router as accounts_router
from claude_code_proxy.api.routes.claude import router as claude_router
from claude_code_proxy.api.routes.health import router as health_router
from claude_code_proxy.api.routes.mcp import setup_mcp
from claude_code_proxy.api.routes.permissions import router as permissions_router
from claude_code_proxy.api.routes.proxy import router as proxy_router
from claude_code_proxy.api.routes.root import router as root_router
from claude_code_proxy.api.routes.settings import router as settings_router
from claude_code_proxy.api.routes.status import router as status_router
from claude_code_proxy.auth.oauth.routes import router as oauth_router
from claude_code_proxy.config.settings import Settings, get_settings
from claude_code_proxy.core.logging import setup_logging
from claude_code_proxy.rotation.startup import (
    initialize_file_watcher_startup,
    initialize_refresh_scheduler_startup,
    initialize_rotation_pool_startup,
    setup_rotation_middleware,
    shutdown_file_watcher,
    shutdown_refresh_scheduler,
    shutdown_rotation_pool,
)
from claude_code_proxy.ui.accounts import mount_accounts_ui
from claude_code_proxy.utils.models_provider import get_models_list
from claude_code_proxy.utils.startup_helpers import (
    check_claude_cli_startup,
    check_version_updates_startup,
    flush_streaming_batches_shutdown,
    initialize_claude_detection_startup,
    initialize_claude_sdk_startup,
    initialize_database_startup,
    initialize_model_resolver_startup,
    initialize_permission_service_startup,
    setup_permission_service_shutdown,
    setup_scheduler_shutdown,
    setup_scheduler_startup,
    setup_session_manager_shutdown,
    shutdown_model_resolver,
    validate_claude_authentication_startup,
)


logger = get_logger(__name__)


# Define lifecycle components for startup/shutdown organization
LIFECYCLE_COMPONENTS: list[LifecycleComponent] = [
    {
        "name": "Database",
        "startup": initialize_database_startup,
        "shutdown": None,  # SQLite connections auto-close, no explicit shutdown needed
    },
    {
        "name": "Claude Authentication",
        "startup": validate_claude_authentication_startup,
        "shutdown": None,  # One-time validation, no cleanup needed
    },
    {
        "name": "Model Resolver",
        "startup": initialize_model_resolver_startup,
        "shutdown": shutdown_model_resolver,
    },
    {
        "name": "Version Check",
        "startup": check_version_updates_startup,
        "shutdown": None,  # One-time check, no cleanup needed
    },
    {
        "name": "Claude CLI",
        "startup": check_claude_cli_startup,
        "shutdown": None,  # Detection only, no cleanup needed
    },
    {
        "name": "Claude Detection",
        "startup": initialize_claude_detection_startup,
        "shutdown": None,  # No cleanup needed
    },
    {
        "name": "Claude SDK",
        "startup": initialize_claude_sdk_startup,
        "shutdown": setup_session_manager_shutdown,
    },
    {
        "name": "Scheduler",
        "startup": setup_scheduler_startup,
        "shutdown": setup_scheduler_shutdown,
    },
    {
        "name": "Permission Service",
        "startup": initialize_permission_service_startup,
        "shutdown": setup_permission_service_shutdown,
    },
    # Multi-account rotation components
    {
        "name": "Rotation Pool",
        "startup": initialize_rotation_pool_startup,
        "shutdown": shutdown_rotation_pool,
    },
    {
        "name": "Token Refresh Scheduler",
        "startup": initialize_refresh_scheduler_startup,
        "shutdown": shutdown_refresh_scheduler,
    },
    {
        "name": "Accounts File Watcher",
        "startup": initialize_file_watcher_startup,
        "shutdown": shutdown_file_watcher,
    },
]

# Additional shutdown-only components that need special handling
SHUTDOWN_ONLY_COMPONENTS: list[ShutdownComponent] = [
    {
        "name": "Streaming Batches",
        "shutdown": flush_streaming_batches_shutdown,
    },
]


# Create shared models router
models_router = APIRouter(tags=["models"])


@models_router.get("/v1/models", response_model=None)
async def list_models() -> dict[str, Any]:
    """List available Claude models.

    Returns a list of available Anthropic Claude models.
    This endpoint is shared between both SDK and proxy APIs.
    """
    return get_models_list()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager using component-based approach."""
    settings = get_settings()
    app.state.settings = settings

    # Startup
    log_server_start(settings)
    log_claude_cli_config(settings)
    await execute_startup_sequence(LIFECYCLE_COMPONENTS, app, settings)

    yield

    # Shutdown
    logger.debug("server_stop")
    await execute_shutdown_sequence(
        LIFECYCLE_COMPONENTS, SHUTDOWN_ONLY_COMPONENTS, app, settings
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        settings: Optional settings override. If None, uses get_settings().

    Returns:
        Configured FastAPI application instance.

    """
    if settings is None:
        settings = get_settings()
    # Configure logging based on settings BEFORE any module uses logger
    # This is needed for reload mode where the app is re-imported

    import structlog

    if not structlog.is_configured():
        # Only setup logging if structlog is not configured at all
        # Always use console output, but respect file logging from settings
        json_logs = False
        setup_logging(
            json_logs=json_logs,
            log_level_name=settings.server.log_level,
            log_file=settings.server.log_file,
        )

    app = FastAPI(
        title="CCProxy API Server",
        description="High-performance Claude Code multi-account proxy server with Anthropic API compatibility",
        version=__version__,
        lifespan=lifespan,
    )

    # Setup middleware
    setup_cors_middleware(app, settings)
    setup_error_handlers(app)

    # Add request content logging middleware first (will run fourth due to middleware order)
    app.add_middleware(RequestContentLoggingMiddleware)

    # Add custom access log middleware second (will run third due to middleware order)
    app.add_middleware(AccessLogMiddleware)

    # Add request ID middleware fourth (will run first to initialize context)
    app.add_middleware(RequestIDMiddleware)

    # Add server header middleware (for non-proxy routes)
    # You can customize the server name here
    app.add_middleware(ServerHeaderMiddleware, server_name="uvicorn")

    # Add API key authentication middleware
    # Protects all routes except public ones when API keys are enabled
    app.add_middleware(APIKeyAuthMiddleware, settings=settings)

    # Add rotation middleware for multi-account support
    # This is added last so it runs first (middleware order is reversed)
    setup_rotation_middleware(app)

    # Include root landing page router (first-run setup redirect)
    app.include_router(root_router, tags=["root"])

    # Include health router (always enabled)
    app.include_router(health_router, tags=["health"])

    # Include accounts export/import router
    app.include_router(accounts_router, tags=["accounts"])

    # Include rotation status router for account monitoring
    app.include_router(status_router, tags=["rotation-status"])

    # Include settings router for model resolution configuration
    app.include_router(settings_router, tags=["settings"])

    app.include_router(oauth_router, prefix="/oauth", tags=["oauth"])

    # Claude SDK routes
    app.include_router(claude_router, prefix="/sdk", tags=["claude-sdk"])

    # Proxy API routes (Anthropic-compatible /v1/messages)
    app.include_router(proxy_router, prefix="/api", tags=["proxy-api"])

    # Shared models endpoints for both SDK and proxy APIs
    app.include_router(models_router, prefix="/sdk", tags=["claude-sdk", "models"])
    app.include_router(models_router, prefix="/api", tags=["proxy-api", "models"])

    # Confirmation endpoints for SSE streaming and responses (conditional on builtin_permissions)
    if settings.claude.builtin_permissions:
        app.include_router(
            permissions_router, prefix="/permissions", tags=["permissions"]
        )
        setup_mcp(app)

    # Mount accounts management UI (HTMX)
    try:
        mount_accounts_ui(app)
    except (OSError, ImportError, ValueError) as e:
        # OS errors (file access), import errors, or validation errors during mount
        logger.warning(
            "accounts_ui_mount_failed",
            error=str(e),
            message="Account management UI not available",
        )

    return app


def get_app() -> FastAPI:
    """Get the FastAPI application instance.

    Returns:
        FastAPI application instance.

    """
    return create_app()
