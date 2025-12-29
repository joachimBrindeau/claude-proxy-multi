"""Utility functions for generating consistent IDs across the application."""

import shortuuid


def generate_client_id() -> str:
    """Generate a consistent client ID for SDK connections.

    Returns:
        str: Short URL-safe ID (22 characters)
    """
    return shortuuid.uuid()
