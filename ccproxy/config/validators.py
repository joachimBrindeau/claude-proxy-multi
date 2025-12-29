"""Configuration validation utilities using Pydantic."""

from pathlib import Path
from typing import Annotated, Any

from pydantic import (
    Field,
    HttpUrl,
    TypeAdapter,
)
from pydantic import (
    ValidationError as PydanticValidationError,
)

from ccproxy.exceptions import ConfigValidationError


# Type aliases using Pydantic Field constraints
Port = Annotated[int, Field(ge=1, le=65535, description="TCP/UDP port number")]
PositiveTimeout = Annotated[float, Field(gt=0, description="Timeout value in seconds")]


def validate_host(host: str) -> str:
    """Validate host address.

    Args:
        host: Host address to validate

    Returns:
        The validated host address

    Raises:
        ConfigValidationError: If host is invalid
    """
    if not host:
        raise ConfigValidationError("Host cannot be empty")

    # Allow common localhost addresses
    if host in ["localhost", "0.0.0.0", "127.0.0.1", "::", "::1"]:
        return host

    # Basic domain name validation (Pydantic's HttpUrl requires scheme)
    # For hosts without scheme, do basic validation
    if "." in host and all(part.strip() for part in host.split(".")):
        return host

    # Allow IP addresses (basic validation)
    if (
        host.replace(".", "")
        .replace(":", "")
        .replace("[", "")
        .replace("]", "")
        .isdigit()
    ):
        return host

    return host


def validate_port(port: int | str) -> int:
    """Validate port number using Pydantic.

    Args:
        port: Port number to validate

    Returns:
        The validated port number

    Raises:
        ConfigValidationError: If port is invalid
    """
    try:
        if isinstance(port, str):
            port = int(port)

        adapter = TypeAdapter(Port)
        return adapter.validate_python(port)
    except (ValueError, PydanticValidationError) as e:
        raise ConfigValidationError(f"Port must be between 1 and 65535: {port}") from e


def validate_url(url: str) -> str:
    """Validate URL format using Pydantic.

    Args:
        url: URL to validate

    Returns:
        The validated URL

    Raises:
        ConfigValidationError: If URL is invalid
    """
    if not url:
        raise ConfigValidationError("URL cannot be empty")

    try:
        adapter = TypeAdapter(HttpUrl)
        validated = adapter.validate_python(url)
        return str(validated)
    except PydanticValidationError as e:
        raise ConfigValidationError(f"Invalid URL: {url}") from e


def validate_path(path: str | Path) -> Path:
    """Validate file path.

    Args:
        path: Path to validate

    Returns:
        The validated Path object

    Raises:
        ConfigValidationError: If path is invalid
    """
    if isinstance(path, str):
        path = Path(path)

    if not isinstance(path, Path):
        raise ConfigValidationError(f"Path must be a string or Path object: {path}")

    return path


def validate_log_level(level: str) -> str:
    """Validate log level.

    Args:
        level: Log level to validate

    Returns:
        The validated log level

    Raises:
        ConfigValidationError: If log level is invalid
    """

    valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    level = level.upper()

    if level not in valid_levels:
        raise ConfigValidationError(
            f"Invalid log level: {level}. Must be one of: {valid_levels}"
        )

    return level


def validate_cors_origins(origins: list[str]) -> list[str]:
    """Validate CORS origins.

    Args:
        origins: List of origin URLs to validate

    Returns:
        The validated list of origins

    Raises:
        ConfigValidationError: If any origin is invalid
    """
    if not isinstance(origins, list):
        raise ConfigValidationError("CORS origins must be a list")

    validated_origins = []
    for origin in origins:
        if origin == "*":
            validated_origins.append(origin)
        else:
            validated_origins.append(validate_url(origin))

    return validated_origins


def validate_timeout(timeout: int | float) -> int | float:
    """Validate timeout value using Pydantic.

    Args:
        timeout: Timeout value to validate

    Returns:
        The validated timeout value

    Raises:
        ConfigValidationError: If timeout is invalid
    """
    try:
        adapter = TypeAdapter(PositiveTimeout)
        return adapter.validate_python(timeout)
    except PydanticValidationError as e:
        raise ConfigValidationError(f"Timeout must be positive: {timeout}") from e


def validate_config_dict(config: dict[str, Any]) -> dict[str, Any]:
    """Validate configuration dictionary.

    Args:
        config: Configuration dictionary to validate

    Returns:
        The validated configuration dictionary

    Raises:
        ConfigValidationError: If configuration is invalid
    """
    if not isinstance(config, dict):
        raise ConfigValidationError("Configuration must be a dictionary")

    validated_config: dict[str, Any] = {}

    # Validate specific fields if present
    if "host" in config:
        validated_config["host"] = validate_host(config["host"])

    if "port" in config:
        validated_config["port"] = validate_port(config["port"])

    if "target_url" in config:
        validated_config["target_url"] = validate_url(config["target_url"])

    if "log_level" in config:
        validated_config["log_level"] = validate_log_level(config["log_level"])

    if "cors_origins" in config:
        validated_config["cors_origins"] = validate_cors_origins(config["cors_origins"])

    if "timeout" in config:
        validated_config["timeout"] = validate_timeout(config["timeout"])

    # Copy other fields without validation
    for key, value in config.items():
        if key not in validated_config:
            validated_config[key] = value

    return validated_config
