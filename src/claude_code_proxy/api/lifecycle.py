"""Application lifecycle management helpers."""

from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import FastAPI
from structlog import get_logger
from typing_extensions import TypedDict

from claude_code_proxy.config.settings import Settings


logger = get_logger(__name__)


# Type definitions for lifecycle components
class LifecycleComponent(TypedDict):
    name: str
    startup: Callable[[FastAPI, Settings], Awaitable[None]] | None
    shutdown: (
        Callable[[FastAPI], Awaitable[None]]
        | Callable[[FastAPI, Settings], Awaitable[None]]
        | None
    )


class ShutdownComponent(TypedDict):
    name: str
    shutdown: Callable[[FastAPI], Awaitable[None]] | None


async def run_startup_component(
    component: LifecycleComponent,
    app: FastAPI,
    settings: Settings,
) -> None:
    """Execute a single startup component with error handling.

    Args:
        component: Lifecycle component definition
        app: FastAPI application instance
        settings: Application settings
    """
    if not component["startup"]:
        return

    component_name = component["name"]
    try:
        logger.debug(f"starting_{component_name.lower().replace(' ', '_')}")
        await component["startup"](app, settings)
    except (OSError, RuntimeError, ValueError) as e:
        logger.error(
            f"{component_name.lower().replace(' ', '_')}_startup_failed",
            error=str(e),
            component=component_name,
        )


async def run_shutdown_component(
    component: LifecycleComponent | ShutdownComponent,
    app: FastAPI,
    settings: Settings | None = None,
) -> None:
    """Execute a single shutdown component with error handling.

    Args:
        component: Lifecycle or shutdown component definition
        app: FastAPI application instance
        settings: Optional application settings (required for some components)
    """
    if not component["shutdown"]:
        return

    component_name = component["name"]
    try:
        logger.debug(f"stopping_{component_name.lower().replace(' ', '_')}")

        # Permission Service needs settings parameter
        if component_name == "Permission Service" and settings:
            await component["shutdown"](settings)  # type: ignore
        else:
            await component["shutdown"](app)  # type: ignore
    except (OSError, RuntimeError) as e:
        logger.error(
            f"{component_name.lower().replace(' ', '_')}_shutdown_failed",
            error=str(e),
            component=component_name,
        )


async def execute_startup_sequence(
    components: list[LifecycleComponent],
    app: FastAPI,
    settings: Settings,
) -> None:
    """Execute all startup components in order.

    Args:
        components: List of lifecycle components
        app: FastAPI application instance
        settings: Application settings
    """
    for component in components:
        await run_startup_component(component, app, settings)


async def execute_shutdown_sequence(
    lifecycle_components: list[LifecycleComponent],
    shutdown_components: list[ShutdownComponent],
    app: FastAPI,
    settings: Settings,
) -> None:
    """Execute all shutdown components in order.

    Args:
        lifecycle_components: List of lifecycle components
        shutdown_components: List of shutdown-only components
        app: FastAPI application instance
        settings: Application settings
    """
    # Execute shutdown-only components first
    for shutdown_component in shutdown_components:
        await run_shutdown_component(shutdown_component, app)

    # Execute shutdown components in reverse order
    for component in reversed(lifecycle_components):
        await run_shutdown_component(component, app, settings)


def log_server_start(settings: Settings) -> None:
    """Log server startup information.

    Args:
        settings: Application settings
    """
    logger.info(
        "server_start",
        host=settings.server.host,
        port=settings.server.port,
        url=f"http://{settings.server.host}:{settings.server.port}",
    )
    logger.debug(
        "server_configured", host=settings.server.host, port=settings.server.port
    )


def log_claude_cli_config(settings: Settings) -> None:
    """Log Claude CLI configuration.

    Args:
        settings: Application settings
    """
    if settings.claude.cli_path:
        logger.debug("claude_cli_configured", cli_path=settings.claude.cli_path)
    else:
        logger.debug("claude_cli_auto_detect")
        logger.debug(
            "claude_cli_search_paths", paths=settings.claude.get_searched_paths()
        )
