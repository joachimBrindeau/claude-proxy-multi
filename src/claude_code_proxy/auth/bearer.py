"""Bearer token authentication implementation."""

from types import TracebackType

from claude_code_proxy.auth.manager import BaseAuthManager
from claude_code_proxy.auth.models import ClaudeCredentials, UserProfile
from claude_code_proxy.exceptions import AuthenticationError


class BearerTokenAuthManager(BaseAuthManager):
    """Authentication manager for static bearer tokens."""

    def __init__(self, token: str) -> None:
        """Initialize with a static bearer token.

        Args:
            token: Bearer token string
        """
        self.token = token.strip()
        if not self.token:
            raise ValueError("Token cannot be empty")

    async def get_access_token(self) -> str:
        """Get the bearer token.

        Returns:
            Bearer token string

        Raises:
            AuthenticationError: If token is invalid
        """
        if not self.token:
            raise AuthenticationError("No bearer token available")
        return self.token

    async def get_credentials(self) -> ClaudeCredentials:
        """Get credentials (not supported for bearer tokens).

        Raises:
            AuthenticationError: Bearer tokens don't support full credentials
        """
        raise AuthenticationError(
            "Bearer token authentication doesn't support full credentials"
        )

    async def is_authenticated(self) -> bool:
        """Check if bearer token is available.

        Returns:
            True if token is available, False otherwise
        """
        return bool(self.token)

    async def get_user_profile(self) -> UserProfile | None:
        """Get user profile (not supported for bearer tokens).

        Returns:
            None - bearer tokens don't support user profiles
        """
        return None

    async def __aenter__(self) -> "BearerTokenAuthManager":
        """Async context manager entry."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Async context manager exit."""
        pass
