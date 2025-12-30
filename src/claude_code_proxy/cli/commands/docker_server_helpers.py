"""Helper functions for Docker server startup - extracted to reduce complexity."""

from structlog import get_logger

from claude_code_proxy.cli.helpers import get_rich_toolkit
from claude_code_proxy.config.settings import Settings
from claude_code_proxy.docker import DockerUserContext


def build_docker_environment(
    settings: Settings,
    docker_env: list[str] | None = None,
) -> dict[str, str]:
    """Build Docker environment variables from settings and CLI overrides.

    Args:
        settings: Application settings containing server configuration
        docker_env: Optional list of environment variables in KEY=VALUE format

    Returns:
        Dictionary of environment variables for Docker container
    """
    docker_env = docker_env or []
    docker_env_dict = {}

    # Parse CLI environment variables
    for env_var in docker_env:
        if "=" in env_var:
            key, value = env_var.split("=", 1)
            docker_env_dict[key] = value

    # Add server configuration to Docker environment
    if settings.server.reload:
        docker_env_dict["RELOAD"] = "true"
    docker_env_dict["PORT"] = str(settings.server.port)
    docker_env_dict["HOST"] = "0.0.0.0"  # nosec B104 - Docker requires 0.0.0.0

    return docker_env_dict


def display_docker_configuration(
    settings: Settings,
    docker_env: list[str],
    docker_env_dict: dict[str, str],
    docker_volume: list[str],
    docker_home: str | None,
    docker_workspace: str | None,
) -> None:
    """Display Docker configuration summary with volumes and environment.

    Args:
        settings: Application settings
        docker_env: List of CLI environment variables
        docker_env_dict: Parsed environment variable dictionary
        docker_volume: List of volume mounts
        docker_home: Override home directory path
        docker_workspace: Override workspace directory path
    """
    toolkit = get_rich_toolkit()

    toolkit.print_line()

    # Show Docker configuration summary
    toolkit.print_title("Docker Configuration Summary", tag="config")

    # Determine effective directories for volume mapping
    home_dir = docker_home or settings.docker.docker_home_directory
    workspace_dir = docker_workspace or settings.docker.docker_workspace_directory

    # Show volume information
    toolkit.print("Volumes:", tag="config")
    if home_dir:
        toolkit.print(f"  Home: {home_dir} → /data/home", tag="volume")
    if workspace_dir:
        toolkit.print(f"  Workspace: {workspace_dir} → /data/workspace", tag="volume")
    if docker_volume:
        for vol in docker_volume:
            toolkit.print(f"  Additional: {vol}", tag="volume")
    toolkit.print_line()

    # Show environment information
    toolkit.print("Environment Variables:", tag="config")
    key_env_vars = {
        "CLAUDE_HOME": "/data/home",
        "CLAUDE_WORKSPACE": "/data/workspace",
        "PORT": str(settings.server.port),
        "HOST": "0.0.0.0",  # nosec B104 - Docker requires 0.0.0.0
    }
    if settings.server.reload:
        key_env_vars["RELOAD"] = "true"

    for key, value in key_env_vars.items():
        toolkit.print(f"  {key}={value}", tag="env")

    # Show additional environment variables from CLI
    for env_var in docker_env:
        toolkit.print(f"  {env_var}", tag="env")

    # Show debug environment information if log level is DEBUG
    if settings.server.log_level == "DEBUG":
        toolkit.print_line()
        toolkit.print_title("Debug: All Environment Variables", tag="debug")
        all_env = {**docker_env_dict}
        for key, value in sorted(all_env.items()):
            toolkit.print(f"  {key}={value}", tag="debug")

    toolkit.print_line()
    toolkit.print_line()


def create_docker_configuration(
    settings: Settings,
    docker_env_dict: dict[str, str],
    docker_image: str | None,
    docker_volume: list[str],
    docker_arg: list[str],
    docker_home: str | None,
    docker_workspace: str | None,
    user_mapping_enabled: bool | None,
    user_uid: int | None,
    user_gid: int | None,
) -> tuple[
    str,
    list[tuple[str, str]],
    dict[str, str],
    list[str] | None,
    DockerUserContext | None,
    list[str],
]:
    """Create Docker adapter configuration from settings.

    Args:
        settings: Application settings
        docker_env_dict: Environment variables dictionary
        docker_image: Override Docker image
        docker_volume: List of volume mounts
        docker_arg: Additional docker arguments
        docker_home: Override home directory
        docker_workspace: Override workspace directory
        user_mapping_enabled: Enable user mapping
        user_uid: User UID for mapping
        user_gid: User GID for mapping

    Returns:
        Tuple of (image, volumes, environment, command, user_context, additional_args)
    """
    from ..docker import _create_docker_adapter_from_settings

    logger = get_logger(__name__)

    image, volumes, environment, command, user_context, additional_args = (
        _create_docker_adapter_from_settings(
            settings,
            command=["ccproxy", "serve"],
            docker_image=docker_image,
            docker_env=[f"{k}={v}" for k, v in docker_env_dict.items()],
            docker_volume=docker_volume,
            docker_arg=docker_arg,
            docker_home=docker_home,
            docker_workspace=docker_workspace,
            user_mapping_enabled=user_mapping_enabled,
            user_uid=user_uid,
            user_gid=user_gid,
        )
    )

    logger.info(
        "docker_server_config",
        configured_image=settings.docker.docker_image,
        effective_image=image,
    )

    return image, volumes, environment, command, user_context, additional_args


def execute_docker_container(
    settings: Settings,
    image: str,
    volumes: list[tuple[str, str]],
    environment: dict[str, str],
    command: list[str] | None,
    user_context: DockerUserContext | None,
) -> None:
    """Execute Docker container with configured settings.

    Args:
        settings: Application settings
        image: Docker image to use
        volumes: List of volume mounts
        environment: Environment variables
        command: Command to execute in container
        user_context: User context for container execution
    """
    from claude_code_proxy.docker import create_docker_adapter

    # Add port mapping
    ports = [f"{settings.server.port}:{settings.server.port}"]

    # Create Docker adapter and execute
    adapter = create_docker_adapter()
    adapter.exec_container(
        image=image,
        volumes=volumes,
        environment=environment,
        command=command,
        user_context=user_context,
        ports=ports,
    )
