"""Token provider for upstream API authentication.

This module handles OAuth token retrieval and rotation account management
for authenticating requests to the Claude API.
"""

from typing import TYPE_CHECKING

import structlog
from fastapi import HTTPException, Request


if TYPE_CHECKING:
    from claude_code_proxy.services.credentials.manager import CredentialsManager

logger = structlog.get_logger(__name__)


class TokenProvider:
    """Provides access tokens for upstream API authentication.

    Handles token retrieval from:
    1. Rotation pool (set by RotationMiddleware)
    2. OAuth credentials from Claude CLI
    """

    def __init__(
        self,
        credentials_manager: "CredentialsManager",
    ) -> None:
        """Initialize the token provider.

        Args:
            credentials_manager: Manager for OAuth credentials
        """
        self.credentials_manager = credentials_manager

    async def get_token(self, request: Request | None = None) -> str:
        """Get access token for upstream authentication.

        Uses rotation account if available, otherwise OAuth credentials from Claude CLI.

        NOTE: The SECURITY__AUTH_TOKEN is only for authenticating incoming requests,
        not for upstream authentication.

        Args:
            request: Optional FastAPI request to check for rotation account

        Returns:
            Valid access token

        Raises:
            HTTPException: If no valid token is available
        """
        # Check for rotation account first (set by RotationMiddleware)
        if request is not None:
            # First check for pre-captured token (avoids race with refresh scheduler)
            rotation_token: str | None = getattr(request.state, "rotation_token", None)
            if rotation_token:
                rotation_account = getattr(request.state, "rotation_account", None)
                account_name = rotation_account.name if rotation_account else "unknown"
                logger.debug(
                    "using_rotation_token",
                    account=account_name,
                )
                return rotation_token

            # Fallback to helper function (for manual account selection)
            from claude_code_proxy.rotation.middleware import get_rotation_token

            rotation_token = get_rotation_token(request)
            if rotation_token:
                rotation_account = getattr(request.state, "rotation_account", None)
                account_name = rotation_account.name if rotation_account else "unknown"
                logger.debug(
                    "using_rotation_token",
                    account=account_name,
                )
                return rotation_token

        # Fall back to OAuth credentials from Claude CLI
        # The SECURITY__AUTH_TOKEN is only for client authentication, not upstream
        try:
            access_token = await self.credentials_manager.get_access_token()
            if not access_token:
                logger.error("oauth_token_unavailable")

                # Try to get more details about credential status
                try:
                    validation = await self.credentials_manager.validate()

                    if (
                        validation.valid
                        and validation.expired
                        and validation.credentials
                    ):
                        logger.debug(
                            "oauth_token_expired",
                            expired_at=str(
                                validation.credentials.claude_ai_oauth.expires_at
                            ),
                        )
                except (ValueError, AttributeError) as e:
                    # ValueError: Invalid credential data
                    # AttributeError: Missing credential fields
                    logger.debug(
                        "credential_check_failed",
                        error=str(e),
                        exc_info=True,
                    )

                raise HTTPException(
                    status_code=401,
                    detail="No valid OAuth credentials found. Please run 'claude-code-proxy auth login'.",
                )

            logger.debug("oauth_token_retrieved")
            return access_token

        except HTTPException:
            raise
        except (OSError, ValueError, RuntimeError) as e:
            # OSError: File system errors reading credentials
            # ValueError: Invalid credential format
            # RuntimeError: Token provider internal errors
            logger.error("oauth_token_retrieval_failed", error=str(e), exc_info=True)
            raise HTTPException(
                status_code=401,
                detail="Authentication failed",
            ) from e
