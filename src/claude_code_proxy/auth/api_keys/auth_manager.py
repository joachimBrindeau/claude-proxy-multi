# src/claude_code_proxy/auth/api_keys/auth_manager.py
"""Auth manager implementation for API key authentication."""

from types import TracebackType

from claude_code_proxy.auth.api_keys.models import APIKey
from claude_code_proxy.auth.manager import BaseAuthManager
from claude_code_proxy.auth.models import AccountInfo, ClaudeCredentials, UserProfile


class APIKeyAuthManager(BaseAuthManager):
    """Auth manager for API key authenticated users."""

    def __init__(self, api_key: APIKey) -> None:
        """Initialize with validated API key.

        Args:
            api_key: Validated API key object

        """
        self._api_key = api_key

    async def get_access_token(self) -> str:
        """Get access token - not applicable for API keys."""
        raise NotImplementedError("API key auth does not provide access tokens")

    async def get_credentials(self) -> ClaudeCredentials:
        """Get credentials info."""
        raise NotImplementedError("API key auth does not provide credentials")

    async def is_authenticated(self) -> bool:
        """Check if authenticated."""
        return not self._api_key.revoked

    async def get_user_profile(self) -> UserProfile | None:
        """Get user profile for API key authenticated users."""
        return UserProfile(
            account=AccountInfo(
                uuid=self._api_key.key_id,
                email=f"{self._api_key.user_id}@api-key",
                full_name=self._api_key.user_id,
                display_name=self._api_key.user_id,
            ),
        )

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Async context manager exit."""
