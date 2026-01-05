"""API key manager - facade for key operations."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import shortuuid
from structlog import get_logger

from claude_code_proxy.auth.api_keys.jwt_handler import JWTHandler
from claude_code_proxy.auth.api_keys.models import APIKey, APIKeyCreate
from claude_code_proxy.auth.api_keys.storage import APIKeyStorage


logger = get_logger(__name__)


class APIKeyManager:
    """Facade for API key operations."""

    def __init__(self, storage_path: Path, secret_key: str) -> None:
        """Initialize the API key manager.

        Args:
            storage_path: Path to JSON file for key metadata
            secret_key: Secret key for JWT signing

        """
        self.storage = APIKeyStorage(storage_path)
        self.jwt_handler = JWTHandler(secret_key)

    def create_key(self, request: APIKeyCreate) -> tuple[APIKey, str]:
        """Create a new API key.

        Args:
            request: Key creation request

        Returns:
            Tuple of (APIKey metadata, JWT token string)

        """
        key_id = f"ccpk_{shortuuid.uuid()[:12]}"  # Claude Code Proxy Key
        now = datetime.now(UTC)

        key = APIKey(
            key_id=key_id,
            user_id=request.user_id,
            description=request.description,
            created_at=now,
            expires_at=now + timedelta(days=request.expires_days),
        )

        token = self.jwt_handler.generate_token(
            user_id=request.user_id,
            key_id=key_id,
            expires_days=request.expires_days,
        )

        self.storage.save(key)
        logger.info(
            "api_key_created",
            key_id=key_id,
            user_id=request.user_id,
            expires_days=request.expires_days,
        )

        return key, token

    def validate_key(self, token: str) -> APIKey | None:
        """Validate an API key token.

        Args:
            token: JWT token string

        Returns:
            APIKey if valid and not revoked, None otherwise

        """
        try:
            payload = self.jwt_handler.validate_token(token)
            key_id = payload["kid"]

            key = self.storage.get(key_id)
            if key is None:
                logger.warning("api_key_not_found", key_id=key_id)
                return None

            if key.revoked:
                logger.warning("api_key_revoked", key_id=key_id)
                return None

            return key

        except ValueError as e:
            logger.warning("api_key_validation_failed", error=str(e))
            return None

    def revoke_key(self, key_id: str) -> bool:
        """Revoke an API key.

        Args:
            key_id: Key ID to revoke

        Returns:
            True if revoked, False if not found

        """
        return self.storage.revoke(key_id)

    def delete_key(self, key_id: str) -> bool:
        """Permanently delete an API key.

        Args:
            key_id: Key ID to delete

        Returns:
            True if deleted, False if not found

        """
        return self.storage.delete(key_id)

    def list_keys(self) -> list[APIKey]:
        """List all API keys.

        Returns:
            List of all keys (including revoked)

        """
        return self.storage.list_all()

    def get_key(self, key_id: str) -> APIKey | None:
        """Get a specific key by ID.

        Args:
            key_id: Key ID

        Returns:
            APIKey if found, None otherwise

        """
        return self.storage.get(key_id)
