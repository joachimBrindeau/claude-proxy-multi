"""Scheduler-specific exceptions.

DEPRECATED: This module is deprecated. Import from ccproxy.exceptions instead.
Re-exports are provided for backwards compatibility.
"""

from ccproxy.exceptions import (
    SchedulerError,
    SchedulerShutdownError,
    TaskExecutionError,
    TaskNotFoundError,
    TaskRegistrationError,
)


__all__ = [
    "SchedulerError",
    "TaskRegistrationError",
    "TaskNotFoundError",
    "TaskExecutionError",
    "SchedulerShutdownError",
]
