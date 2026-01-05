"""Constants for the rotation module.

This module centralizes configuration values used across the rotation package.
"""

# Time constants (in seconds unless otherwise noted)
DEFAULT_HTTP_TIMEOUT_SECONDS = 30.0
DEFAULT_TOKEN_EXPIRY_SECONDS = 3600  # 1 hour
ONE_HOUR_MILLISECONDS = 60 * 60 * 1000
FILE_WATCHER_SHUTDOWN_TIMEOUT_SECONDS = 5.0

# Retry-After header value for rate-limited responses
RATE_LIMIT_RETRY_AFTER_SECONDS = "3600"

# Paths that trigger account rotation
ROTATION_ENABLED_PATHS: tuple[str, ...] = (
    "/api/v1/chat/completions",
    "/api/v1/messages",
    "/sdk/v1/messages",
)
