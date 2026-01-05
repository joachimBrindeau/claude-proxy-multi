"""Tests for API key manager."""

from pathlib import Path

import pytest

from claude_code_proxy.auth.api_keys.manager import APIKeyManager
from claude_code_proxy.auth.api_keys.models import APIKeyCreate


class TestAPIKeyManager:
    """Tests for API key manager facade."""

    @pytest.fixture
    def manager(self, tmp_path: Path) -> APIKeyManager:
        """Create a manager with temporary storage."""
        return APIKeyManager(
            storage_path=tmp_path / "api_keys.json",
            secret_key="test-secret-key-32-chars-long!!",
        )

    def test_create_key(self, manager: APIKeyManager) -> None:
        """Test creating a new API key."""
        create_request = APIKeyCreate(user_id="john", expires_days=90)

        key, token = manager.create_key(create_request)

        assert key.user_id == "john"
        assert token is not None
        assert len(token) > 50

    def test_validate_key(self, manager: APIKeyManager) -> None:
        """Test validating a key token."""
        create_request = APIKeyCreate(user_id="john", expires_days=90)
        key, token = manager.create_key(create_request)

        result = manager.validate_key(token)

        assert result is not None
        assert result.user_id == "john"

    def test_validate_revoked_key_fails(self, manager: APIKeyManager) -> None:
        """Test that revoked keys fail validation."""
        create_request = APIKeyCreate(user_id="john", expires_days=90)
        key, token = manager.create_key(create_request)

        manager.revoke_key(key.key_id)

        result = manager.validate_key(token)
        assert result is None

    def test_list_keys(self, manager: APIKeyManager) -> None:
        """Test listing all keys."""
        manager.create_key(APIKeyCreate(user_id="john", expires_days=90))
        manager.create_key(APIKeyCreate(user_id="jane", expires_days=90))

        keys = manager.list_keys()

        assert len(keys) == 2
