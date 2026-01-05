"""JSON file storage for API keys."""

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import orjson
from structlog import get_logger

from claude_code_proxy.auth.api_keys.models import APIKey


logger = get_logger(__name__)


class APIKeyStorage:
    """JSON file storage for API key metadata."""

    def __init__(self, file_path: Path) -> None:
        """Initialize storage with file path.

        Args:
            file_path: Path to the JSON file for storing keys

        """
        self.file_path = file_path

    def _load_all(self) -> dict[str, dict[str, Any]]:
        """Load all keys from file.

        Returns:
            Dictionary mapping key IDs to key data

        """
        if not self.file_path.exists():
            return {}

        try:
            data = orjson.loads(self.file_path.read_bytes())
            keys: dict[str, dict[str, Any]] = data.get("keys", {})
            return keys
        except orjson.JSONDecodeError:
            logger.exception("api_key_storage_json_decode_error")
            return {}
        except OSError:
            logger.exception(
                "api_key_storage_file_read_error",
                path=str(self.file_path),
            )
            return {}

    def _save_all(self, keys: dict[str, dict[str, Any]]) -> None:
        """Save all keys to file.

        Args:
            keys: Dictionary mapping key IDs to key data

        Raises:
            OSError: If file write fails

        """
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        data = {"keys": keys, "version": 1}
        self.file_path.write_bytes(orjson.dumps(data, option=orjson.OPT_INDENT_2))

    def save(self, key: APIKey) -> None:
        """Save or update an API key.

        Args:
            key: API key to save

        """
        keys = self._load_all()
        keys[key.key_id] = key.model_dump(mode="json")
        self._save_all(keys)
        logger.info("api_key_saved", key_id=key.key_id, user_id=key.user_id)

    def get(self, key_id: str) -> APIKey | None:
        """Get an API key by ID.

        Args:
            key_id: Key identifier

        Returns:
            APIKey if found, None otherwise

        """
        keys = self._load_all()
        if key_id not in keys:
            return None
        return APIKey.model_validate(keys[key_id])

    def list_all(self) -> list[APIKey]:
        """List all API keys.

        Returns:
            List of all API keys

        """
        keys = self._load_all()
        return [APIKey.model_validate(v) for v in keys.values()]

    def delete(self, key_id: str) -> bool:
        """Delete an API key.

        Args:
            key_id: Key to delete

        Returns:
            True if deleted, False if not found

        """
        keys = self._load_all()
        if key_id not in keys:
            return False
        del keys[key_id]
        self._save_all(keys)
        logger.info("api_key_deleted", key_id=key_id)
        return True

    def revoke(self, key_id: str) -> bool:
        """Revoke an API key (soft delete).

        Args:
            key_id: Key to revoke

        Returns:
            True if revoked, False if not found

        """
        key = self.get(key_id)
        if key is None:
            return False
        key.revoked = True
        key.revoked_at = datetime.now(UTC)
        self.save(key)
        logger.info("api_key_revoked", key_id=key_id)
        return True
