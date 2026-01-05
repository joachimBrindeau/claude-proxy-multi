"""Startup utility functions for application lifecycle management.

This module contains simple utility functions to extract and organize
the complex startup logic from the main lifespan function, following
the KISS principle and avoiding overengineering.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import structlog
from fastapi import FastAPI

from claude_code_proxy.auth.credentials_adapter import CredentialsAuthManager
from claude_code_proxy.exceptions import (
    ClaudeSDKError,
    CredentialsError,
    CredentialsExpiredError,
    CredentialsNotFoundError,
    CredentialsStorageError,
    PermissionRequestError,
    SchedulerError,
)
from claude_code_proxy.scheduler.manager import start_scheduler, stop_scheduler
from claude_code_proxy.services.claude_detection_service import ClaudeDetectionService
from claude_code_proxy.services.claude_sdk_service import ClaudeSDKService
from claude_code_proxy.services.credentials.manager import CredentialsManager


# Note: get_permission_service is imported locally to avoid circular imports

if TYPE_CHECKING:
    from claude_code_proxy.config.settings import Settings

logger = structlog.get_logger(__name__)


async def initialize_database_startup(app: FastAPI, settings: Settings) -> None:
    """Initialize SQLite database and migrate existing accounts.json if present.

    This must run early in the startup sequence before components that depend on
    database access (rotation pool, OAuth flows, etc.).

    Args:
        app: FastAPI application instance
        settings: Application settings

    """
    try:
        from claude_code_proxy.db import init_db, migrate_from_accounts_json
        from claude_code_proxy.rotation.accounts import DEFAULT_ACCOUNTS_PATH

        # Initialize SQLite database (creates tables if needed)
        await init_db()
        logger.debug("database_initialized")

        # Migrate existing accounts.json if present
        if DEFAULT_ACCOUNTS_PATH.exists():
            migrated = await migrate_from_accounts_json(DEFAULT_ACCOUNTS_PATH)
            if migrated > 0:
                logger.info("startup_migrated_accounts", count=migrated)
    except (ImportError, OSError, RuntimeError, ValueError) as e:
        logger.exception(
            "database_initialization_failed",
            error=str(e),
            message="Failed to initialize database. Some features may not work.",
        )


async def validate_claude_authentication_startup(
    app: FastAPI, settings: Settings
) -> None:
    """Validate Claude authentication credentials at startup.

    Args:
        app: FastAPI application instance
        settings: Application settings

    """
    try:
        credentials_manager = CredentialsManager()
        validation = await credentials_manager.validate()

        if validation.valid and not validation.expired:
            credentials = validation.credentials
            oauth_token = credentials.claude_ai_oauth if credentials else None

            if oauth_token and oauth_token.expires_at_datetime:
                hours_until_expiry = int(
                    (
                        oauth_token.expires_at_datetime - datetime.now(UTC)
                    ).total_seconds()
                    / 3600
                )
                logger.debug(
                    "claude_token_valid",
                    expires_in_hours=hours_until_expiry,
                    subscription_type=oauth_token.subscription_type,
                    credentials_path=str(validation.path) if validation.path else None,
                )
            else:
                logger.debug(
                    "claude_token_valid", credentials_path=str(validation.path)
                )
        elif validation.expired:
            logger.warning(
                "claude_token_expired",
                message="Claude authentication token has expired. Please run 'claude-code-proxy auth login' to refresh.",
                credentials_path=str(validation.path) if validation.path else None,
            )
        else:
            logger.warning(
                "claude_token_invalid",
                message="Claude authentication token is invalid. Please run 'claude-code-proxy auth login'.",
                credentials_path=str(validation.path) if validation.path else None,
            )
    except CredentialsNotFoundError:
        logger.warning(
            "claude_token_not_found",
            message="No Claude authentication credentials found. Please run 'claude-code-proxy auth login' to authenticate.",
            searched_paths=settings.auth.storage.storage_paths,
        )
    # Catch credential-related errors (storage issues, validation failures, etc.)
    except (CredentialsError, CredentialsStorageError, ValueError, OSError) as e:
        logger.exception(
            "claude_token_validation_error",
            error=str(e),
            message="Failed to validate Claude authentication token. The server will continue without Claude authentication.",
        )
    except Exception as e:
        logger.exception(
            "claude_token_validation_error",
            error=str(e),
            message="Failed to validate Claude authentication token. The server will continue without Claude authentication.",
        )


async def check_version_updates_startup(app: FastAPI, settings: Settings) -> None:
    """Trigger version update check at startup.

    Manually runs the version check task once during application startup,
    before the scheduler starts managing periodic checks.

    Args:
        app: FastAPI application instance
        settings: Application settings

    """
    # Skip version check if disabled by settings
    if not settings.scheduler.version_check_enabled:
        logger.debug("version_check_startup_disabled")
        return

    try:
        # Import locally to avoid circular imports and create task instance
        from claude_code_proxy.scheduler.tasks import VersionUpdateCheckTask

        # Create a temporary task instance for startup check
        version_task = VersionUpdateCheckTask(
            name="version_check_startup",
            interval_seconds=settings.scheduler.version_check_interval_hours * 3600,
            enabled=True,
            version_check_cache_ttl_hours=settings.scheduler.version_check_cache_ttl_hours,
            skip_first_scheduled_run=False,
        )

        # Run the version check once and wait for it to complete
        success = await version_task.run()

        if success:
            logger.debug("version_check_startup_completed")
        else:
            logger.debug("version_check_startup_failed")

    # Catch import errors, scheduler errors, and network/runtime issues during version check
    except (ImportError, SchedulerError, RuntimeError, OSError, ValueError) as e:
        logger.debug(
            "version_check_startup_error",
            error=str(e),
            error_type=type(e).__name__,
        )


async def check_claude_cli_startup(app: FastAPI, settings: Settings) -> None:
    """Check Claude CLI availability at startup.

    Args:
        app: FastAPI application instance
        settings: Application settings

    """
    try:
        from claude_code_proxy.api.routes.health import get_claude_cli_info

        claude_info = await get_claude_cli_info()

        if claude_info.status == "available":
            logger.info(
                "claude_cli_available",
                status=claude_info.status,
                version=claude_info.version,
                binary_path=claude_info.binary_path,
            )
        else:
            logger.warning(
                "claude_cli_unavailable",
                status=claude_info.status,
                error=claude_info.error,
                binary_path=claude_info.binary_path,
                message=f"Claude CLI status: {claude_info.status}",
            )
    # Catch import errors, subprocess failures, and file system errors during CLI check
    except (ImportError, OSError, RuntimeError, ValueError) as e:
        logger.exception(
            "claude_cli_check_failed",
            error=str(e),
            message="Failed to check Claude CLI status during startup",
        )
    except Exception as e:
        logger.exception(
            "claude_cli_check_failed",
            error=str(e),
            message="Failed to check Claude CLI status during startup",
        )


async def setup_scheduler_startup(app: FastAPI, settings: Settings) -> None:
    """Start scheduler system and configure tasks.

    Args:
        app: FastAPI application instance
        settings: Application settings

    """
    try:
        scheduler = await start_scheduler(settings)
        app.state.scheduler = scheduler
        logger.debug("scheduler_initialized")

        # Add session pool stats task if session manager is available
        if (
            scheduler
            and hasattr(app.state, "session_manager")
            and app.state.session_manager
        ):
            try:
                # Add session pool stats task that runs every minute
                await scheduler.add_task(
                    task_name="session_pool_stats",
                    task_type="pool_stats",
                    interval_seconds=60,  # Every minute
                    enabled=True,
                    pool_manager=app.state.session_manager,
                )
                logger.debug("session_pool_stats_task_added", interval_seconds=60)
            # Catch scheduler task registration errors
            except SchedulerError as e:
                logger.exception(
                    "session_pool_stats_task_add_failed",
                    error=str(e),
                    error_type=type(e).__name__,
                )
    except SchedulerError as e:
        logger.exception("scheduler_initialization_failed", error=str(e))
        # Continue startup even if scheduler fails (graceful degradation)


async def setup_scheduler_shutdown(app: FastAPI) -> None:
    """Stop scheduler system.

    Args:
        app: FastAPI application instance

    """
    try:
        scheduler = getattr(app.state, "scheduler", None)
        await stop_scheduler(scheduler)
        logger.debug("scheduler_stopped_lifespan")
    except SchedulerError as e:
        logger.exception("scheduler_stop_failed", error=str(e))


async def setup_session_manager_shutdown(app: FastAPI) -> None:
    """Shutdown Claude SDK session manager if it was created.

    Args:
        app: FastAPI application instance

    """
    if hasattr(app.state, "session_manager") and app.state.session_manager:
        try:
            await app.state.session_manager.shutdown()
            logger.debug("claude_sdk_session_manager_shutdown")
        # Catch SDK session shutdown errors (connection cleanup, process termination)
        except (ClaudeSDKError, RuntimeError, OSError) as e:
            logger.exception("claude_sdk_session_manager_shutdown_failed", error=str(e))
        except Exception as e:
            logger.exception("claude_sdk_session_manager_shutdown_failed", error=str(e))


async def initialize_claude_detection_startup(app: FastAPI, settings: Settings) -> None:
    """Initialize Claude detection service.

    Args:
        app: FastAPI application instance
        settings: Application settings

    """
    try:
        logger.debug("initializing_claude_detection")
        detection_service = ClaudeDetectionService(settings)
        claude_data = await detection_service.initialize_detection()
        app.state.claude_detection_data = claude_data
        app.state.claude_detection_service = detection_service
        logger.debug(
            "claude_detection_completed",
            version=claude_data.claude_version,
            cached_at=claude_data.cached_at.isoformat(),
        )
    # Catch detection errors (subprocess failures, parsing errors, file access)
    except (OSError, RuntimeError, ValueError) as e:
        logger.exception("claude_detection_startup_failed", error=str(e))
        # Continue startup with fallback - detection service will provide fallback data
        detection_service = ClaudeDetectionService(settings)
        app.state.claude_detection_data = detection_service._get_fallback_data()
        app.state.claude_detection_service = detection_service
    except Exception as e:
        logger.exception("claude_detection_startup_failed", error=str(e))
        # Continue startup with fallback - detection service will provide fallback data
        detection_service = ClaudeDetectionService(settings)
        app.state.claude_detection_data = detection_service._get_fallback_data()
        app.state.claude_detection_service = detection_service


async def initialize_claude_sdk_startup(app: FastAPI, settings: Settings) -> None:
    """Initialize ClaudeSDKService and store in app state.

    Args:
        app: FastAPI application instance
        settings: Application settings

    """
    try:
        # Create auth manager with settings
        auth_manager = CredentialsAuthManager()

        # Check if session pool should be enabled from settings configuration
        use_session_pool = settings.claude.sdk_session_pool.enabled

        # Initialize session manager if session pool is enabled
        session_manager = None
        if use_session_pool:
            from claude_code_proxy.claude_sdk.manager import SessionManager

            # Create SessionManager with dependency injection
            session_manager = SessionManager(settings=settings)

            # Start the session manager (initializes session pool if enabled)
            await session_manager.start()

        # Create ClaudeSDKService instance
        claude_service = ClaudeSDKService(
            auth_manager=auth_manager,
            settings=settings,
            session_manager=session_manager,
        )

        # Store in app state for reuse in dependencies
        app.state.claude_service = claude_service
        app.state.session_manager = (
            session_manager  # Store session_manager for shutdown
        )
        logger.debug("claude_sdk_service_initialized")
    # Catch SDK initialization errors (import, auth, session pool, config)
    except (ImportError, ClaudeSDKError, CredentialsError, RuntimeError, OSError) as e:
        logger.exception("claude_sdk_service_initialization_failed", error=str(e))
        # Continue startup even if ClaudeSDKService fails (graceful degradation)
    except Exception as e:
        logger.exception("claude_sdk_service_initialization_failed", error=str(e))
        # Continue startup even if ClaudeSDKService fails (graceful degradation)


async def initialize_permission_service_startup(
    app: FastAPI, settings: Settings
) -> None:
    """Initialize permission service (conditional on builtin_permissions).

    Args:
        app: FastAPI application instance
        settings: Application settings

    """
    if settings.claude.builtin_permissions:
        try:
            from claude_code_proxy.api.services.permission_service import (
                get_permission_service,
            )

            permission_service = get_permission_service()

            # Log if external handler is expected
            if not settings.server.use_terminal_permission_handler:
                logger.debug(
                    "permission_handler_configured",
                    handler_type="external_sse",
                    message="Terminal permission handler disabled - use 'claude-code-proxy permission-handler connect' to handle permissions",
                )
                logger.warning(
                    "permission_handler_required",
                    message="Start external handler with: claude-code-proxy permission-handler connect",
                )

            # Start the permission service
            await permission_service.start()

            # Store references in app state
            app.state.permission_service = permission_service

            logger.debug(
                "permission_service_initialized",
                timeout_seconds=permission_service._timeout_seconds,
                terminal_handler_enabled=settings.server.use_terminal_permission_handler,
                builtin_permissions_enabled=True,
            )
        # Catch permission service init errors (import, async start, config)
        except (ImportError, PermissionRequestError, RuntimeError, OSError) as e:
            logger.exception("permission_service_initialization_failed", error=str(e))
            # Continue without permission service (API will work but without prompts)
    else:
        logger.debug(
            "permission_service_skipped",
            builtin_permissions_enabled=False,
            message="Built-in permission handling disabled - users can configure custom MCP servers and permission tools",
        )


async def setup_permission_service_shutdown(app: FastAPI, settings: Settings) -> None:
    """Stop permission service (if it was initialized).

    Args:
        app: FastAPI application instance
        settings: Application settings

    """
    if (
        hasattr(app.state, "permission_service")
        and app.state.permission_service
        and settings.claude.builtin_permissions
    ):
        try:
            await app.state.permission_service.stop()
            logger.debug("permission_service_stopped")
        # Catch permission service shutdown errors (async cleanup, connection close)
        except (PermissionRequestError, RuntimeError, OSError) as e:
            logger.exception("permission_service_stop_failed", error=str(e))


async def flush_streaming_batches_shutdown(app: FastAPI) -> None:
    """Flush any remaining streaming log batches.

    Args:
        app: FastAPI application instance

    """
    try:
        from claude_code_proxy.utils.simple_request_logger import (
            flush_all_streaming_batches,
        )

        await flush_all_streaming_batches()
        logger.debug("streaming_batches_flushed")
    # Catch streaming batch flush errors (import, I/O, async cleanup)
    except (ImportError, OSError, RuntimeError) as e:
        logger.exception("streaming_batches_flush_failed", error=str(e))
    except Exception as e:
        logger.exception("streaming_batches_flush_failed", error=str(e))


async def initialize_model_resolver_startup(app: FastAPI, settings: Settings) -> None:
    """Initialize the dynamic model resolver and fallback system.

    Fetches available models from Anthropic's API and caches
    tier-to-model mappings for dynamic alias resolution.
    Also initializes the model fallback system for 403 error handling.

    Args:
        app: FastAPI application instance
        settings: Application settings

    """
    try:
        from claude_code_proxy.services.model_fallback import (
            ModelTier,
            initialize_model_fallback,
        )
        from claude_code_proxy.services.model_resolver import (
            ModelResolver,
            set_model_resolver,
        )

        credentials_manager = CredentialsManager()

        # Default: 15 minutes (900 seconds)
        resolver = ModelResolver(
            credentials_manager=credentials_manager,
            refresh_interval_seconds=900,
        )

        await resolver.initialize()

        # Set global resolver for use in model_mapping.py
        set_model_resolver(resolver)

        # Initialize the model fallback system
        availability_cache, fallback_resolver = initialize_model_fallback()

        # Populate fallback resolver with models by tier
        tier_models = resolver.get_models_by_tier()
        fallback_models = {
            ModelTier(tier): models
            for tier, models in tier_models.items()
            if tier in [t.value for t in ModelTier]
        }
        fallback_resolver.set_models_by_tier(fallback_models)

        # Store in app state for access
        app.state.model_resolver = resolver
        app.state.availability_cache = availability_cache
        app.state.fallback_resolver = fallback_resolver

        logger.info(
            "model_resolver_initialized",
            cached_tiers=list(resolver.get_cached_mappings().keys()),
            fallback_enabled=True,
        )
    # Catch model resolver init errors (import, network, credentials)
    except (
        ImportError,
        RuntimeError,
        OSError,
        ValueError,
        CredentialsExpiredError,
        CredentialsError,
    ) as e:
        logger.warning(
            "model_resolver_initialization_failed",
            error=str(e),
            fallback="static_mappings",
            message="Using static model mappings as fallback. Refresh credentials at /accounts",
        )
        # Continue startup - model_mapping.py has static fallbacks


async def shutdown_model_resolver(app: FastAPI) -> None:
    """Shutdown the model resolver, fallback system, and clean up resources.

    Args:
        app: FastAPI application instance

    """
    # Shutdown fallback system first
    try:
        from claude_code_proxy.services.model_fallback import shutdown_model_fallback

        shutdown_model_fallback()
        logger.debug("model_fallback_shutdown")
    except (ImportError, RuntimeError) as e:
        logger.exception("model_fallback_shutdown_failed", error=str(e))

    # Then shutdown model resolver
    if hasattr(app.state, "model_resolver") and app.state.model_resolver:
        try:
            from claude_code_proxy.services.model_resolver import set_model_resolver

            await app.state.model_resolver.close()
            set_model_resolver(None)
            logger.debug("model_resolver_shutdown")
        # Catch model resolver shutdown errors (HTTP client cleanup)
        except (RuntimeError, OSError) as e:
            logger.exception("model_resolver_shutdown_failed", error=str(e))
