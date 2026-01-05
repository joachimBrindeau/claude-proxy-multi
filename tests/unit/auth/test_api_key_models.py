# tests/unit/auth/test_api_key_models.py
"""Tests for API key models."""

from datetime import UTC, datetime

from claude_code_proxy.auth.api_keys.models import APIKey, APIKeyCreate


class TestAPIKeyModel:
    """Tests for APIKey Pydantic model."""

    def test_api_key_creation(self) -> None:
        """Test creating an APIKey instance."""
        key = APIKey(
            key_id="test-key-123",
            user_id="john",
            description="Test key",
            created_at=datetime.now(UTC),
            expires_at=datetime.now(UTC),
        )
        assert key.key_id == "test-key-123"
        assert key.user_id == "john"
        assert key.revoked is False

    def test_api_key_create_model(self) -> None:
        """Test APIKeyCreate input model."""
        create = APIKeyCreate(user_id="john", expires_days=90)
        assert create.user_id == "john"
        assert create.expires_days == 90
