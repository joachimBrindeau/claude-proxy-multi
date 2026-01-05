"""Docker adapter factory for CLI commands.

This module provides functions to create Docker adapters from CLI settings
and command-line arguments.
"""

import getpass
from pathlib import Path
from typing import Any

from claude_code_proxy.config.docker_settings import DockerSettings
from claude_code_proxy.config.settings import Settings
from claude_code_proxy.docker import (
    DockerEnv,
    DockerPath,
    DockerUserContext,
    DockerVolume,
)


def _parse_volume_string(vol_str: str) -> DockerVolume | None:
    """Parse a volume string into a DockerVolume tuple.

    Args:
        vol_str: Volume string in format "host:container[:options]"

    Returns:
        Tuple of (host_path, container_path) or None if invalid

    """
    parts = vol_str.split(":", 2)
    if len(parts) >= 2:
        return (parts[0], parts[1])
    return None


def _build_volumes(
    docker_settings: DockerSettings,
    docker_home: str | None,
    docker_workspace: str | None,
    docker_volume: list[str] | None,
) -> list[DockerVolume]:
    """Build list of Docker volumes from settings and overrides.

    Args:
        docker_settings: Docker configuration from settings
        docker_home: Override home directory
        docker_workspace: Override workspace directory
        docker_volume: Additional volume mappings from CLI

    Returns:
        List of volume tuples (host_path, container_path)

    """
    volumes: list[DockerVolume] = []

    # Add home/workspace volumes with effective directories
    home_dir = docker_home or docker_settings.docker_home_directory
    workspace_dir = docker_workspace or docker_settings.docker_workspace_directory

    if home_dir:
        volumes.append((str(Path(home_dir)), "/data/home"))
    if workspace_dir:
        volumes.append((str(Path(workspace_dir)), "/data/workspace"))

    # Add base volumes from settings
    for vol_str in docker_settings.docker_volumes:
        volume = _parse_volume_string(vol_str)
        if volume:
            volumes.append(volume)

    # Add CLI override volumes
    if docker_volume:
        for vol_str in docker_volume:
            volume = _parse_volume_string(vol_str)
            if volume:
                volumes.append(volume)

    return volumes


def _build_environment(
    docker_settings: DockerSettings,
    docker_home: str | None,
    docker_workspace: str | None,
    docker_env: list[str] | None,
) -> DockerEnv:
    """Build Docker environment variables from settings and overrides.

    Args:
        docker_settings: Docker configuration from settings
        docker_home: Override home directory
        docker_workspace: Override workspace directory
        docker_env: Additional environment variables from CLI

    Returns:
        Dictionary of environment variables

    """
    environment: DockerEnv = docker_settings.docker_environment.copy()

    # Add home/workspace environment variables
    home_dir = docker_home or docker_settings.docker_home_directory
    workspace_dir = docker_workspace or docker_settings.docker_workspace_directory

    if home_dir:
        environment["CLAUDE_HOME"] = "/data/home"
    if workspace_dir:
        environment["CLAUDE_WORKSPACE"] = "/data/workspace"

    # Add CLI override environment
    if docker_env:
        for env_var in docker_env:
            if "=" in env_var:
                key, value = env_var.split("=", 1)
                environment[key] = value

    return environment


def _create_docker_paths(
    home_dir: str | None, workspace_dir: str | None
) -> tuple[DockerPath | None, DockerPath | None]:
    """Create DockerPath instances for home and workspace directories.

    Args:
        home_dir: Home directory path
        workspace_dir: Workspace directory path

    Returns:
        Tuple of (home_path, workspace_path), each may be None

    """
    home_path = None
    workspace_path = None

    if home_dir:
        home_path = DockerPath(host_path=Path(home_dir), container_path="/data/home")
    if workspace_dir:
        workspace_path = DockerPath(
            host_path=Path(workspace_dir), container_path="/data/workspace"
        )

    return home_path, workspace_path


def _build_user_context(
    docker_settings: DockerSettings,
    docker_home: str | None,
    docker_workspace: str | None,
    user_mapping_enabled: bool | None,
    user_uid: int | None,
    user_gid: int | None,
) -> DockerUserContext | None:
    """Build Docker user context from settings and overrides.

    Args:
        docker_settings: Docker configuration from settings
        docker_home: Override home directory
        docker_workspace: Override workspace directory
        user_mapping_enabled: Override user mapping setting
        user_uid: Override user ID
        user_gid: Override group ID

    Returns:
        DockerUserContext if user mapping is enabled and valid, None otherwise

    """
    effective_mapping_enabled = (
        user_mapping_enabled
        if user_mapping_enabled is not None
        else docker_settings.user_mapping_enabled
    )

    if not effective_mapping_enabled:
        return None

    effective_uid = user_uid if user_uid is not None else docker_settings.user_uid
    effective_gid = user_gid if user_gid is not None else docker_settings.user_gid

    if effective_uid is None or effective_gid is None:
        return None

    # Determine effective directories
    home_dir = docker_home or docker_settings.docker_home_directory
    workspace_dir = docker_workspace or docker_settings.docker_workspace_directory

    # Create DockerPath instances
    home_path, workspace_path = _create_docker_paths(home_dir, workspace_dir)

    # Use current username
    username = getpass.getuser()

    return DockerUserContext(
        uid=effective_uid,
        gid=effective_gid,
        username=username,
        home_path=home_path,
        workspace_path=workspace_path,
    )


def _build_command(
    command: list[str] | None, cmd_args: list[str] | None
) -> list[str] | None:
    """Build final command from command and arguments.

    Args:
        command: Base command to run
        cmd_args: Additional arguments for the command

    Returns:
        Combined command list or None if no command provided

    """
    if not command:
        return None

    final_command = command.copy()
    if cmd_args:
        final_command.extend(cmd_args)

    return final_command


def _create_docker_adapter_from_settings(
    settings: Settings,
    docker_image: str | None = None,
    docker_env: list[str] | None = None,
    docker_volume: list[str] | None = None,
    docker_arg: list[str] | None = None,
    docker_home: str | None = None,
    docker_workspace: str | None = None,
    user_mapping_enabled: bool | None = None,
    user_uid: int | None = None,
    user_gid: int | None = None,
    command: list[str] | None = None,
    cmd_args: list[str] | None = None,
    **kwargs: Any,
) -> tuple[
    str,
    list[DockerVolume],
    DockerEnv,
    list[str] | None,
    DockerUserContext | None,
    list[str],
]:
    """Convert settings and overrides to Docker adapter parameters.

    Args:
        settings: Application settings
        docker_image: Override Docker image
        docker_env: Additional environment variables
        docker_volume: Additional volume mappings
        docker_arg: Additional Docker arguments
        docker_home: Override home directory
        docker_workspace: Override workspace directory
        user_mapping_enabled: Override user mapping setting
        user_uid: Override user ID
        user_gid: Override group ID
        command: Command to run in container
        cmd_args: Arguments for the command
        **kwargs: Additional keyword arguments (ignored)

    Returns:
        Tuple of (image, volumes, environment, command, user_context, additional_args)

    """
    docker_settings = settings.docker

    # Determine effective image
    image = docker_image or docker_settings.docker_image

    # Build components using helper functions
    volumes = _build_volumes(
        docker_settings, docker_home, docker_workspace, docker_volume
    )
    environment = _build_environment(
        docker_settings, docker_home, docker_workspace, docker_env
    )
    user_context = _build_user_context(
        docker_settings,
        docker_home,
        docker_workspace,
        user_mapping_enabled,
        user_uid,
        user_gid,
    )
    final_command = _build_command(command, cmd_args)

    # Additional Docker arguments
    additional_args = docker_settings.docker_additional_args.copy()
    if docker_arg:
        additional_args.extend(docker_arg)

    return image, volumes, environment, final_command, user_context, additional_args
