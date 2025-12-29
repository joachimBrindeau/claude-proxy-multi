from pathlib import Path

import platformdirs


def get_xdg_config_home() -> Path:
    """Get the XDG_CONFIG_HOME directory using platformdirs.

    Returns:
        Path to the user config directory (cross-platform).
    """
    return Path(platformdirs.user_config_dir())


def get_xdg_data_home() -> Path:
    """Get the XDG_DATA_HOME directory using platformdirs.

    Returns:
        Path to the user data directory (cross-platform).
    """
    return Path(platformdirs.user_data_dir())


def get_xdg_cache_home() -> Path:
    """Get the XDG_CACHE_HOME directory using platformdirs.

    Returns:
        Path to the user cache directory (cross-platform).
    """
    return Path(platformdirs.user_cache_dir())
