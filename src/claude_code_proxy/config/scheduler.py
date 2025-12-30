"""Scheduler configuration settings."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class SchedulerSettings(BaseSettings):
    """
    Configuration settings for the unified scheduler system.

    Controls global scheduler behavior and individual task configurations.
    Settings can be configured via environment variables with SCHEDULER__ prefix.
    """

    # Global scheduler settings
    enabled: bool = Field(
        default=True,
        description="Whether the scheduler system is enabled",
    )

    max_concurrent_tasks: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum number of tasks that can run concurrently",
    )

    graceful_shutdown_timeout: float = Field(
        default=30.0,
        ge=1.0,
        le=300.0,
        description="Timeout in seconds for graceful task shutdown",
    )

    # Version checking task settings
    version_check_enabled: bool = Field(
        default=True,
        description="Whether version update checking is enabled. Enabled by default for privacy - checks GitHub API when enabled",
    )

    version_check_interval_hours: int = Field(
        default=6,
        ge=1,
        le=168,  # Max 1 week
        description="Interval in hours between version checks",
    )

    version_check_cache_ttl_hours: float = Field(
        default=6,
        ge=0.1,
        le=24.0,
        description="Maximum age in hours since last check version check",
    )

    model_config = SettingsConfigDict(
        env_prefix="SCHEDULER__",
        case_sensitive=False,
    )
