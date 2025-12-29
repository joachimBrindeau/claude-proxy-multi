"""Scheduler management for FastAPI integration."""

import structlog

from ccproxy.config.settings import Settings

from .core import Scheduler
from .errors import SchedulerError, SchedulerShutdownError, TaskRegistrationError
from .registry import register_task
from .tasks import (
    PoolStatsTask,
    VersionUpdateCheckTask,
)


logger = structlog.get_logger(__name__)


async def setup_scheduler_tasks(scheduler: Scheduler, settings: Settings) -> None:
    """
    Setup and configure all scheduler tasks based on settings.

    Args:
        scheduler: Scheduler instance
        settings: Application settings
    """
    scheduler_config = settings.scheduler

    if not scheduler_config.enabled:
        logger.info("scheduler_disabled")
        return

    # Log network features status
    logger.info(
        "network_features_status",
        version_check_enabled=scheduler_config.version_check_enabled,
        message=(
            "Network features disabled by default for privacy"
            if not scheduler_config.version_check_enabled
            else "Some network features are enabled"
        ),
    )

    # Add version update check task if enabled
    if scheduler_config.version_check_enabled:
        try:
            # Convert hours to seconds
            interval_seconds = scheduler_config.version_check_interval_hours * 3600

            await scheduler.add_task(
                task_name="version_update_check",
                task_type="version_update_check",
                interval_seconds=interval_seconds,
                enabled=True,
                version_check_cache_ttl_hours=scheduler_config.version_check_cache_ttl_hours,
            )
            logger.debug(
                "version_check_task_added",
                interval_hours=scheduler_config.version_check_interval_hours,
                version_check_cache_ttl_hours=scheduler_config.version_check_cache_ttl_hours,
            )
        except (SchedulerError, TaskRegistrationError) as e:
            # Task registration or scheduler state errors during task addition
            logger.error(
                "version_check_task_add_failed",
                error=str(e),
                error_type=type(e).__name__,
            )


def _register_default_tasks(settings: Settings) -> None:
    """Register default task types in the global registry based on configuration."""
    from .registry import get_task_registry

    registry = get_task_registry()

    # Register core tasks
    if not registry.is_registered("version_update_check"):
        register_task("version_update_check", VersionUpdateCheckTask)
    if not registry.is_registered("pool_stats"):
        register_task("pool_stats", PoolStatsTask)


async def start_scheduler(settings: Settings) -> Scheduler | None:
    """
    Start the scheduler with configured tasks.

    Args:
        settings: Application settings

    Returns:
        Scheduler instance if successful, None otherwise
    """
    try:
        if not settings.scheduler.enabled:
            logger.info("scheduler_disabled")
            return None

        # Register task types (only when actually starting scheduler)
        _register_default_tasks(settings)

        # Create scheduler with settings
        scheduler = Scheduler(
            max_concurrent_tasks=settings.scheduler.max_concurrent_tasks,
            graceful_shutdown_timeout=settings.scheduler.graceful_shutdown_timeout,
        )

        # Start the scheduler
        await scheduler.start()

        # Setup tasks based on configuration
        await setup_scheduler_tasks(scheduler, settings)

        logger.info(
            "scheduler_started",
            max_concurrent_tasks=settings.scheduler.max_concurrent_tasks,
            active_tasks=scheduler.task_count,
            running_tasks=len(
                [
                    name
                    for name in scheduler.list_tasks()
                    if scheduler.get_task(name).is_running
                ]
            ),
        )

        return scheduler

    except SchedulerError as e:
        # Scheduler initialization or task setup failed
        logger.error(
            "scheduler_start_failed",
            error=str(e),
            error_type=type(e).__name__,
        )
        return None


async def stop_scheduler(scheduler: Scheduler | None) -> None:
    """
    Stop the scheduler gracefully.

    Args:
        scheduler: Scheduler instance to stop
    """
    if scheduler is None:
        return

    try:
        await scheduler.stop()
    except SchedulerShutdownError as e:
        # Graceful shutdown failed or timed out
        logger.error(
            "scheduler_stop_failed",
            error=str(e),
            error_type=type(e).__name__,
        )
