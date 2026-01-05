"""Credential loading and profile helpers for authentication commands.

This module contains helper functions to load credentials and fetch user profiles,
reducing complexity in the main auth commands.
"""

import asyncio

import httpx
from structlog import get_logger

from claude_code_proxy.auth.models import ClaudeCredentials, UserProfile
from claude_code_proxy.exceptions import CredentialsError, OAuthError
from claude_code_proxy.services.credentials import CredentialsManager


logger = get_logger(__name__)


async def get_or_fetch_profile(
    manager: CredentialsManager,
) -> UserProfile | None:
    """Get saved profile or fetch a fresh one if not available.

    This function first tries to load a saved account profile. If that's not available,
    it attempts to fetch a fresh profile from the API and save it for future use.

    Args:
        manager: Credentials manager instance

    Returns:
        Account profile if available, None otherwise

    """
    # Try to load saved profile first
    profile = await manager.get_account_profile()
    if profile:
        return profile

    # No saved profile, try to fetch fresh data
    return await fetch_and_save_profile(manager)


async def fetch_and_save_profile(
    manager: CredentialsManager,
) -> UserProfile | None:
    """Fetch a fresh profile from the API and save it.

    This function attempts to get a valid access token (refreshing if needed),
    fetch the user profile, and save it for future use.

    Args:
        manager: Credentials manager instance

    Returns:
        Account profile if successfully fetched, None otherwise

    """
    try:
        # First try to get a valid access token (with refresh if needed)
        valid_token = await manager.get_access_token()
        if not valid_token:
            logger.debug("Token refresh failed")
            return None

        # Fetch the profile
        profile = await manager.fetch_user_profile()
        if not profile:
            logger.debug("Could not fetch user profile")
            return None

        # Save the profile for future use
        await manager._save_account_profile(profile)
        return profile

    except (httpx.HTTPError, OAuthError, CredentialsError) as e:
        # Network errors or credential issues when fetching profile
        logger.debug(f"Could not fetch user profile: {e}")
        return None


async def reload_credentials_after_refresh(
    manager: CredentialsManager,
) -> ClaudeCredentials | None:
    """Reload credentials after a potential token refresh.

    After fetching a profile (which may trigger a token refresh), we need to
    reload the credentials to get the updated token information.

    Args:
        manager: Credentials manager instance

    Returns:
        Reloaded credentials, or None if loading fails

    """
    try:
        return await manager.load()
    except CredentialsError as e:
        logger.debug(f"Could not reload credentials: {e}")
        return None


def get_profile_sync(manager: CredentialsManager) -> UserProfile | None:
    """Get or fetch profile synchronously.

    Args:
        manager: Credentials manager instance

    Returns:
        Account profile if available, None otherwise

    """
    return asyncio.run(get_or_fetch_profile(manager))
