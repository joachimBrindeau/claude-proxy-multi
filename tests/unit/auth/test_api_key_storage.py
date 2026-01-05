# tests/unit/auth/test_api_key_storage.py
"""Tests for API key storage."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from claude_code_proxy.auth.api_keys.models import APIKey
from claude_code_proxy.auth.api_keys.storage import APIKeyStorage


class TestAPIKeyStorage:
    """Tests for API key JSON storage."""

    @pytest.fixture
    def temp_storage(self, tmp_path: Path) -> APIKeyStorage:
        """Create a temporary storage instance."""
        return APIKeyStorage(file_path=tmp_path / "api_keys.json")

    def test_save_and_load_key(self, temp_storage: APIKeyStorage) -> None:
        """Test saving and loading an API key."""
        key = APIKey(
            key_id="test-123",
            user_id="john",
            description="Test key",
            created_at=datetime.now(UTC),
            expires_at=datetime.now(UTC) + timedelta(days=90),
        )

        temp_storage.save(key)
        loaded = temp_storage.get("test-123")

        assert loaded is not None
        assert loaded.key_id == "test-123"
        assert loaded.user_id == "john"

    def test_list_keys(self, temp_storage: APIKeyStorage) -> None:
        """Test listing all keys."""
        key1 = APIKey(
            key_id="key-1",
            user_id="john",
            expires_at=datetime.now(UTC) + timedelta(days=90),
        )
        key2 = APIKey(
            key_id="key-2",
            user_id="jane",
            expires_at=datetime.now(UTC) + timedelta(days=90),
        )

        temp_storage.save(key1)
        temp_storage.save(key2)

        keys = temp_storage.list_all()
        assert len(keys) == 2

    def test_delete_key(self, temp_storage: APIKeyStorage) -> None:
        """Test deleting a key."""
        key = APIKey(
            key_id="to-delete",
            user_id="john",
            expires_at=datetime.now(UTC) + timedelta(days=90),
        )
        temp_storage.save(key)

        temp_storage.delete("to-delete")

        assert temp_storage.get("to-delete") is None

    def test_revoke_key(self, temp_storage: APIKeyStorage) -> None:
        """Test revoking a key."""
        key = APIKey(
            key_id="to-revoke",
            user_id="john",
            expires_at=datetime.now(UTC) + timedelta(days=90),
        )
        temp_storage.save(key)

        temp_storage.revoke("to-revoke")

        loaded = temp_storage.get("to-revoke")
        assert loaded is not None
        assert loaded.revoked is True
        assert loaded.revoked_at is not None
