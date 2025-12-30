from pathlib import Path

from claude_code_proxy.core.system import get_xdg_cache_home, get_xdg_config_home


def find_toml_config_file() -> Path | None:
    """Find the TOML configuration file for claude_code_proxy.

    Searches in the following order:
    1. .claude_code_proxy.toml in current directory
    2. claude_code_proxy.toml in git repository root (if in a git repo)
    3. config.toml in user config directory/ccproxy/ (platform-specific)
    """
    # Check current directory first
    candidates = [
        Path(".claude_code_proxy.toml").resolve(),
        Path("claude_code_proxy.toml").resolve(),
    ]

    # Check git repo root
    git_root = find_git_root()
    if git_root:
        candidates.extend(
            [
                git_root / ".claude_code_proxy.toml",
                git_root / "claude_code_proxy.toml",
            ]
        )

    # Check XDG config directory
    config_dir = get_ccproxy_config_dir()
    candidates.append(config_dir / "config.toml")

    # Return first existing file
    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate

    return None


def find_git_root(path: Path | None = None) -> Path | None:
    """Find the root directory of a git repository."""
    import subprocess  # nosec B404 - safe usage for git commands only

    if path is None:
        path = Path.cwd()

    try:
        # nosec B603, B607 - safe: hardcoded git command, no user input
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=path,
            capture_output=True,
            text=True,
            check=True,
        )
        return Path(result.stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def get_ccproxy_config_dir() -> Path:
    """Get the ccproxy configuration directory.

    Returns:
        Path to the ccproxy configuration directory within user config directory.
    """
    return get_xdg_config_home() / "claude_code_proxy"


def get_claude_cli_config_dir() -> Path:
    """Get the Claude CLI configuration directory.

    Returns:
        Path to the Claude CLI configuration directory within user config directory.
    """
    return get_xdg_config_home() / "claude"


def get_claude_docker_home_dir() -> Path:
    """Get the Claude Docker home directory.

    Returns:
        Path to the Claude Docker home directory within ccproxy config directory.
    """
    return get_ccproxy_config_dir() / "home"


def get_ccproxy_cache_dir() -> Path:
    """Get the ccproxy cache directory.

    Returns:
        Path to the ccproxy cache directory within user cache directory.
    """
    return get_xdg_cache_home() / "claude_code_proxy"
