"""Settings configuration for Claude Proxy API Server."""

import contextlib
import os
import tomllib
from pathlib import Path
from typing import Any

import orjson
import structlog
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from claude_code_proxy.config.discovery import find_toml_config_file
from claude_code_proxy.core.validators import parse_comma_separated

from .auth import AuthSettings
from .claude import ClaudeSettings
from .cors import CORSSettings
from .docker_settings import DockerSettings
from .reverse_proxy import ReverseProxySettings
from .scheduler import SchedulerSettings
from .security import SecuritySettings
from .server import ServerSettings


__all__ = [
    "Settings",
    "ConfigurationError",
    "ConfigurationManager",
    "config_manager",
    "get_settings",
]


class ConfigurationError(Exception):
    """Raised when configuration loading or validation fails."""

    pass


def _coerce_settings(value: Any, settings_class: type) -> Any:
    """Coerce value to settings class instance.

    Handles: None → default, dict → instance, passthrough existing instances.
    """
    if value is None:
        return settings_class()
    if isinstance(value, settings_class):
        return value
    if isinstance(value, dict):
        return settings_class(**value)
    # Handle objects with model_dump or __dict__
    if hasattr(value, "model_dump"):
        return settings_class(**value.model_dump())
    if hasattr(value, "__dict__"):
        return settings_class(**value.__dict__)
    return value


class Settings(BaseSettings):
    """
    Configuration settings for the Claude Proxy API Server.

    Settings are loaded from environment variables, .env files, and TOML configuration files.
    Environment variables take precedence over .env file values.
    TOML configuration files are loaded in the following order:
    1. .claude_code_proxy.toml in current directory
    2. claude_code_proxy.toml in git repository root
    3. config.toml in user config directory/claude-code-proxy/ (platform-specific)
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        env_nested_delimiter="__",
    )

    # Core application settings
    server: ServerSettings = Field(
        default_factory=ServerSettings,
        description="Server configuration settings",
    )

    security: SecuritySettings = Field(
        default_factory=SecuritySettings,
        description="Security configuration settings",
    )

    cors: CORSSettings = Field(
        default_factory=CORSSettings,
        description="CORS configuration settings",
    )

    # Claude-specific settings
    claude: ClaudeSettings = Field(
        default_factory=ClaudeSettings,
        description="Claude-specific configuration settings",
    )

    # Proxy and authentication
    reverse_proxy: ReverseProxySettings = Field(
        default_factory=ReverseProxySettings,
        description="Reverse proxy configuration settings",
    )

    auth: AuthSettings = Field(
        default_factory=AuthSettings,
        description="Authentication and credentials configuration",
    )

    # Container settings
    docker: DockerSettings = Field(
        default_factory=DockerSettings,
        description="Docker configuration for running Claude commands in containers",
    )

    # Scheduler settings
    scheduler: SchedulerSettings = Field(
        default_factory=SchedulerSettings,
        description="Task scheduler configuration settings",
    )

    @field_validator("server", mode="before")
    @classmethod
    def validate_server(cls, v: Any) -> Any:
        return _coerce_settings(v, ServerSettings)

    @field_validator("security", mode="before")
    @classmethod
    def validate_security(cls, v: Any) -> Any:
        return _coerce_settings(v, SecuritySettings)

    @field_validator("cors", mode="before")
    @classmethod
    def validate_cors(cls, v: Any) -> Any:
        return _coerce_settings(v, CORSSettings)

    @field_validator("claude", mode="before")
    @classmethod
    def validate_claude(cls, v: Any) -> Any:
        return _coerce_settings(v, ClaudeSettings)

    @field_validator("reverse_proxy", mode="before")
    @classmethod
    def validate_reverse_proxy(cls, v: Any) -> Any:
        return _coerce_settings(v, ReverseProxySettings)

    @field_validator("auth", mode="before")
    @classmethod
    def validate_auth(cls, v: Any) -> Any:
        return _coerce_settings(v, AuthSettings)

    @field_validator("docker", mode="before")
    @classmethod
    def validate_docker_settings(cls, v: Any) -> Any:
        return _coerce_settings(v, DockerSettings)

    @field_validator("scheduler", mode="before")
    @classmethod
    def validate_scheduler(cls, v: Any) -> Any:
        return _coerce_settings(v, SchedulerSettings)

    @property
    def server_url(self) -> str:
        """Get the complete server URL."""
        return f"http://{self.server.host}:{self.server.port}"

    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.server.reload or self.server.log_level == "DEBUG"

    @model_validator(mode="after")
    def setup_claude_cli_path(self) -> "Settings":
        """Set up Claude CLI path in environment if provided or found."""
        # If not explicitly set, try to find it
        if not self.claude.cli_path:
            found_path, found_in_path = self.claude.find_claude_cli()
            if found_path:
                self.claude.cli_path = found_path
                # Only add to PATH if it wasn't found via which()
                if not found_in_path:
                    cli_dir = str(Path(self.claude.cli_path).parent)
                    current_path = os.environ.get("PATH", "")
                    if cli_dir not in current_path:
                        os.environ["PATH"] = f"{cli_dir}:{current_path}"
        elif self.claude.cli_path:
            # If explicitly set, always add to PATH
            cli_dir = str(Path(self.claude.cli_path).parent)
            current_path = os.environ.get("PATH", "")
            if cli_dir not in current_path:
                os.environ["PATH"] = f"{cli_dir}:{current_path}"
        return self

    def model_dump_safe(self) -> dict[str, Any]:
        """
        Dump model data with sensitive information masked.

        Returns:
            dict: Configuration with sensitive data masked
        """
        return self.model_dump()

    @classmethod
    def load_toml_config(cls, toml_path: Path) -> dict[str, Any]:
        """Load configuration from a TOML file.

        Args:
            toml_path: Path to the TOML configuration file

        Returns:
            dict: Configuration data from the TOML file

        Raises:
            ValueError: If the TOML file is invalid or cannot be read
        """
        try:
            with toml_path.open("rb") as f:
                return tomllib.load(f)
        except OSError as e:
            raise ValueError(f"Cannot read TOML config file {toml_path}: {e}") from e
        except tomllib.TOMLDecodeError as e:
            raise ValueError(f"Invalid TOML syntax in {toml_path}: {e}") from e

    @classmethod
    def load_config_file(cls, config_path: Path) -> dict[str, Any]:
        """Load configuration from a file based on its extension.

        Args:
            config_path: Path to the configuration file

        Returns:
            dict: Configuration data from the file

        Raises:
            ValueError: If the file format is unsupported or invalid
        """
        suffix = config_path.suffix.lower()

        if suffix in [".toml"]:
            return cls.load_toml_config(config_path)
        else:
            raise ValueError(
                f"Unsupported config file format: {suffix}. "
                "Only TOML (.toml) files are supported."
            )

    @classmethod
    def from_toml(cls, toml_path: Path | None = None, **kwargs: Any) -> "Settings":
        """Create Settings instance from TOML configuration.

        Args:
            toml_path: Path to TOML configuration file. If None, auto-discovers file.
            **kwargs: Additional keyword arguments to override config values

        Returns:
            Settings: Configured Settings instance
        """
        # Use the more generic from_config method
        return cls.from_config(config_path=toml_path, **kwargs)

    @classmethod
    def from_config(
        cls, config_path: Path | str | None = None, **kwargs: Any
    ) -> "Settings":
        """Create Settings instance from configuration file.

        Args:
            config_path: Path to configuration file. Can be:
                - None: Auto-discover config file or use CONFIG_FILE env var
                - Path or str: Use this specific config file
            **kwargs: Additional keyword arguments to override config values

        Returns:
            Settings: Configured Settings instance
        """
        # Check for CONFIG_FILE environment variable first
        if config_path is None:
            config_path_env = os.environ.get("CONFIG_FILE")
            if config_path_env:
                config_path = Path(config_path_env)

        # Convert string to Path if needed
        if isinstance(config_path, str):
            config_path = Path(config_path)

        # Auto-discover config file if not provided
        if config_path is None:
            config_path = find_toml_config_file()

        # Load config if found
        config_data = {}
        if config_path and config_path.exists():
            config_data = cls.load_config_file(config_path)

        # Merge config with kwargs (kwargs take precedence)
        merged_config = {**config_data, **kwargs}

        # Create Settings instance with merged config
        return cls(**merged_config)


class ConfigurationManager:
    """Centralized configuration management for CLI and server."""

    def __init__(self) -> None:
        self._settings: Settings | None = None
        self._config_path: Path | None = None
        self._logging_configured = False

    def load_settings(
        self,
        config_path: Path | None = None,
        cli_overrides: dict[str, Any] | None = None,
    ) -> Settings:
        """Load settings with CLI overrides and caching."""
        if self._settings is None or config_path != self._config_path:
            try:
                self._settings = Settings.from_config(
                    config_path=config_path, **(cli_overrides or {})
                )
                self._config_path = config_path
            except (OSError, ValueError, tomllib.TOMLDecodeError) as e:
                # OS errors (file access), validation errors, or TOML parsing errors
                raise ConfigurationError(f"Failed to load configuration: {e}") from e

        return self._settings

    def setup_logging(self, log_level: str | None = None) -> None:
        """Configure logging once based on settings."""
        if self._logging_configured:
            return
        self._logging_configured = True

    @staticmethod
    def _extract_config_section(
        cli_args: dict[str, Any], keys: list[str]
    ) -> dict[str, Any]:
        """Extract non-None values for specified keys from CLI args.

        Args:
            cli_args: CLI arguments dictionary
            keys: List of keys to extract

        Returns:
            Dictionary with non-None values
        """
        return {key: cli_args[key] for key in keys if cli_args.get(key) is not None}

    @staticmethod
    def _build_pool_config(
        claude_settings: dict[str, Any], cli_args: dict[str, Any]
    ) -> None:
        """Build pool configuration from CLI args.

        Args:
            claude_settings: Claude settings dict to update (modified in place)
            cli_args: CLI arguments
        """
        if cli_args.get("sdk_pool") is not None:
            claude_settings["sdk_pool"] = {"enabled": cli_args["sdk_pool"]}

        if cli_args.get("sdk_pool_size") is not None:
            if "sdk_pool" not in claude_settings:
                claude_settings["sdk_pool"] = {}
            claude_settings["sdk_pool"]["pool_size"] = cli_args["sdk_pool_size"]

        if cli_args.get("sdk_session_pool") is not None:
            claude_settings["sdk_session_pool"] = {
                "enabled": cli_args["sdk_session_pool"]
            }

    def get_cli_overrides_from_args(self, **cli_args: Any) -> dict[str, Any]:
        """Extract non-None CLI arguments as configuration overrides."""
        overrides: dict[str, Any] = {}

        # Server settings
        server_settings = self._extract_config_section(
            cli_args, ["host", "port", "reload", "log_level", "log_file"]
        )
        if server_settings:
            overrides["server"] = server_settings

        # Security settings
        if cli_args.get("auth_token") is not None:
            overrides["security"] = {"auth_token": cli_args["auth_token"]}

        # Claude settings
        claude_settings: dict[str, Any] = {}
        if cli_args.get("claude_cli_path") is not None:
            claude_settings["cli_path"] = cli_args["claude_cli_path"]

        # Direct Claude settings
        claude_settings.update(
            self._extract_config_section(
                cli_args,
                [
                    "sdk_message_mode",
                    "system_prompt_injection_mode",
                    "builtin_permissions",
                ],
            )
        )

        # Pool configuration
        self._build_pool_config(claude_settings, cli_args)

        # Claude Code options
        claude_opts = self._extract_config_section(
            cli_args,
            [
                "max_thinking_tokens",
                "permission_mode",
                "cwd",
                "max_turns",
                "append_system_prompt",
                "permission_prompt_tool_name",
                "continue_conversation",
            ],
        )

        # Handle comma-separated lists
        for key in ["allowed_tools", "disallowed_tools"]:
            if cli_args.get(key):
                claude_opts[key] = parse_comma_separated(cli_args[key])

        if claude_opts:
            claude_settings["code_options"] = claude_opts

        if claude_settings:
            overrides["claude"] = claude_settings

        # CORS settings
        if cli_args.get("cors_origins"):
            overrides["cors"] = {
                "origins": parse_comma_separated(cli_args["cors_origins"])
            }

        return overrides

    def reset(self) -> None:
        """Reset configuration state (useful for testing)."""
        self._settings = None
        self._config_path = None
        self._logging_configured = False


# Global configuration manager instance
config_manager = ConfigurationManager()

logger = structlog.get_logger(__name__)


def get_settings(config_path: Path | str | None = None) -> Settings:
    """Get the global settings instance with configuration file support.

    Args:
        config_path: Optional path to configuration file. If None, uses CONFIG_FILE env var
                    or auto-discovers config file.

    Returns:
        Settings: Configured Settings instance
    """
    try:
        # Check for CLI overrides from environment variable
        cli_overrides = {}
        cli_overrides_json = os.environ.get("CLAUDE_CODE_PROXY_CONFIG_OVERRIDES")
        if cli_overrides_json:
            with contextlib.suppress(ValueError):
                cli_overrides = orjson.loads(cli_overrides_json)

        settings = Settings.from_config(config_path=config_path, **cli_overrides)
        return settings
    except (OSError, ValueError, tomllib.TOMLDecodeError) as e:
        # OS errors (file access), validation errors, or TOML parsing errors
        # If settings can't be loaded, this will be handled by the caller
        raise ValueError(f"Configuration error: {e}") from e
