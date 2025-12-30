"""Startup and shutdown helpers for rotation components.

Integrates with ccproxy's lifecycle management.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

import orjson
from fastapi import FastAPI
from structlog import get_logger

from claude_code_proxy.rotation.file_watcher import (
    init_file_watcher,
)
from claude_code_proxy.rotation.middleware import RotationMiddleware
from claude_code_proxy.rotation.pool import init_rotation_pool
from claude_code_proxy.rotation.refresh import init_refresh_scheduler


if TYPE_CHECKING:
    from claude_code_proxy.config.settings import Settings


logger = get_logger(__name__)


class InvalidAccountsPathError(ValueError):
    """Raised when CCPROXY_ACCOUNTS_PATH is invalid."""

    pass


def _validate_accounts_path(path_str: str) -> None:
    """Validate that an accounts path is valid.

    Args:
        path_str: Path string to validate

    Raises:
        InvalidAccountsPathError: If path is not absolute or parent doesn't exist
    """
    if not path_str.startswith(("/", "~")):
        raise InvalidAccountsPathError(
            f"CCPROXY_ACCOUNTS_PATH must be an absolute path or start with ~, "
            f"got: {path_str!r}"
        )
    expanded = Path(path_str).expanduser()
    parent = expanded.parent
    if not parent.exists():
        raise InvalidAccountsPathError(f"Parent directory does not exist: {parent}")


def get_accounts_path(*, validate: bool = False) -> Path:
    """Get accounts file path from environment or default.

    Args:
        validate: If True, validate that the path is absolute or starts with ~,
                 and parent directory exists. Raises InvalidAccountsPathError on failure.

    Returns:
        Path to accounts.json

    Raises:
        InvalidAccountsPathError: If validate=True and path is invalid
    """
    env_path = os.environ.get("CCPROXY_ACCOUNTS_PATH")

    if env_path:
        if validate:
            _validate_accounts_path(env_path)
        return Path(env_path).expanduser()

    return Path("~/.claude/accounts.json").expanduser()


def is_rotation_enabled() -> bool:
    """Check if rotation should be enabled.

    Rotation is enabled if:
    1. CCPROXY_ROTATION_ENABLED env var is set to "true" (or not "false")
    2. AND accounts.json file exists

    Returns:
        True if rotation should be enabled
    """
    # Check environment variable
    env_enabled = os.environ.get("CCPROXY_ROTATION_ENABLED", "true").lower()
    if env_enabled == "false":
        logger.info("rotation_disabled_by_env")
        return False

    # Check if accounts file exists
    accounts_path = get_accounts_path()
    if not accounts_path.exists():
        logger.info(
            "rotation_disabled_no_accounts_file",
            path=str(accounts_path),
            message="Create accounts.json to enable multi-account rotation",
        )
        return False

    return True


async def initialize_rotation_pool_startup(app: FastAPI, settings: Settings) -> None:
    """Initialize the rotation pool on startup.

    Note: The pool is typically already created by setup_rotation_middleware().
    This function ensures the pool exists and logs initialization status.

    Args:
        app: FastAPI application
        settings: Application settings
    """
    # Check if pool was already created by middleware setup
    existing_pool = getattr(app.state, "rotation_pool", None)
    if existing_pool is not None:
        logger.info(
            "rotation_pool_already_initialized",
            accounts=existing_pool.account_count,
            available=existing_pool.available_count,
        )
        return

    # No pool yet - check if rotation should be enabled
    if not is_rotation_enabled():
        app.state.rotation_pool = None
        app.state.rotation_enabled = False
        return

    # Create pool (fallback if middleware setup didn't run)
    try:
        accounts_path = get_accounts_path()
        pool = init_rotation_pool(accounts_path)

        app.state.rotation_pool = pool
        app.state.rotation_enabled = True

        logger.info(
            "rotation_pool_initialized",
            accounts=pool.account_count,
            available=pool.available_count,
            path=str(accounts_path),
        )

    except FileNotFoundError:
        logger.warning(
            "rotation_pool_no_accounts",
            message="Accounts file not found, rotation disabled",
        )
        app.state.rotation_pool = None
        app.state.rotation_enabled = False

    except (OSError, orjson.JSONDecodeError, ValueError) as e:
        # OSError: File system errors (permissions, disk full)
        # orjson.JSONDecodeError: Invalid JSON in accounts file
        # ValueError: Invalid account data structure or validation errors
        logger.error(
            "rotation_pool_init_failed",
            error=str(e),
        )
        app.state.rotation_pool = None
        app.state.rotation_enabled = False


async def initialize_refresh_scheduler_startup(
    app: FastAPI, settings: Settings
) -> None:
    """Initialize the token refresh scheduler on startup.

    Args:
        app: FastAPI application
        settings: Application settings
    """
    if not getattr(app.state, "rotation_enabled", False):
        app.state.refresh_scheduler = None
        return

    pool = getattr(app.state, "rotation_pool", None)
    if pool is None:
        app.state.refresh_scheduler = None
        return

    try:
        scheduler = init_refresh_scheduler(pool)
        await scheduler.start()

        app.state.refresh_scheduler = scheduler

        logger.info("token_refresh_scheduler_initialized")

    except (RuntimeError, ValueError) as e:
        # RuntimeError: Scheduler failed to start (event loop issues)
        # ValueError: Invalid scheduler configuration
        logger.error(
            "refresh_scheduler_init_failed",
            error=str(e),
        )
        app.state.refresh_scheduler = None


async def shutdown_refresh_scheduler(app: FastAPI) -> None:
    """Shutdown the token refresh scheduler.

    Args:
        app: FastAPI application
    """
    scheduler = getattr(app.state, "refresh_scheduler", None)
    if scheduler:
        await scheduler.stop()
        logger.info("token_refresh_scheduler_stopped")


async def shutdown_rotation_pool(app: FastAPI) -> None:
    """Cleanup rotation pool on shutdown.

    Args:
        app: FastAPI application
    """
    pool = getattr(app.state, "rotation_pool", None)
    if pool:
        # Save any pending state
        pool.save()
        logger.info("rotation_pool_saved")


async def initialize_file_watcher_startup(app: FastAPI, settings: Settings) -> None:
    """Initialize the file watcher for hot-reload on startup.

    Args:
        app: FastAPI application
        settings: Application settings
    """
    if not getattr(app.state, "rotation_enabled", False):
        app.state.file_watcher = None
        return

    pool = getattr(app.state, "rotation_pool", None)
    if pool is None:
        app.state.file_watcher = None
        return

    # Check if hot-reload is enabled (default: true)
    hot_reload_enabled = os.environ.get("CCPROXY_HOT_RELOAD", "true").lower()
    if hot_reload_enabled == "false":
        logger.info("file_watcher_disabled_by_env")
        app.state.file_watcher = None
        return

    try:
        accounts_path = get_accounts_path()

        async def on_reload() -> None:
            """Async callback when accounts file changes.

            Uses pool lock for thread-safe reload.
            """
            try:
                # Acquire pool lock for thread-safe access
                async with pool._lock:
                    if pool.reload_if_changed():
                        logger.info(
                            "accounts_hot_reloaded",
                            accounts=pool.account_count,
                            available=pool.available_count,
                        )
            except (OSError, orjson.JSONDecodeError, ValueError) as e:
                # OSError: File read errors during reload
                # orjson.JSONDecodeError: Invalid JSON in modified accounts file
                # ValueError: Invalid account data after reload
                logger.error("accounts_hot_reload_failed", error=str(e))

        watcher = init_file_watcher(accounts_path, on_reload)
        watcher.start()

        app.state.file_watcher = watcher

        logger.info(
            "file_watcher_initialized",
            watching=str(accounts_path),
        )

    except (OSError, ValueError) as e:
        # OSError: File system errors when setting up watcher
        # ValueError: Invalid path or configuration
        logger.error(
            "file_watcher_init_failed",
            error=str(e),
        )
        app.state.file_watcher = None


async def shutdown_file_watcher(app: FastAPI) -> None:
    """Shutdown the file watcher.

    Args:
        app: FastAPI application
    """
    watcher = getattr(app.state, "file_watcher", None)
    if watcher:
        watcher.stop()
        logger.info("file_watcher_stopped")


def setup_rotation_middleware(app: FastAPI) -> None:
    """Add rotation middleware to the application.

    Should be called during app creation, after pool initialization.
    Creates the pool instance that will be shared with all components.

    Args:
        app: FastAPI application
    """
    # Check if rotation is enabled - this is called before lifespan
    # so we can't check app.state yet. Check via file existence.
    if not is_rotation_enabled():
        logger.debug("rotation_middleware_skipped", reason="rotation_not_enabled")
        return

    accounts_path = get_accounts_path()
    try:
        # Create ONE pool instance and use it everywhere
        # This pool is stored in app.state and used by:
        # - The rotation middleware (for request handling)
        # - The status routes (for monitoring)
        # - The refresh scheduler (for token refresh)
        pool = init_rotation_pool(accounts_path)

        # Store pool in app state for other components
        app.state.rotation_pool = pool
        app.state.rotation_enabled = True

        app.add_middleware(RotationMiddleware, pool=pool)

        logger.info(
            "rotation_middleware_added",
            accounts=pool.account_count,
        )

    except FileNotFoundError:
        logger.warning("rotation_middleware_skipped", reason="no_accounts_file")
    except (OSError, orjson.JSONDecodeError, ValueError) as e:
        # OSError: File system errors reading accounts
        # orjson.JSONDecodeError: Invalid JSON in accounts file
        # ValueError: Invalid account data or middleware configuration
        logger.error("rotation_middleware_setup_failed", error=str(e))
