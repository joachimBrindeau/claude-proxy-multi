# tests/unit/auth/test_auth_dependencies_api_keys.py
"""Tests for API key integration in auth dependencies."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.security import HTTPAuthorizationCredentials

from claude_code_proxy.auth.dependencies import _get_auth_manager_with_settings


class TestAPIKeyAuthIntegration:
    """Tests for API key auth in dependencies."""

    @pytest.fixture
    def mock_settings(self, tmp_path: Path) -> MagicMock:
        """Create mock settings with API keys enabled."""
        settings = MagicMock()
        settings.security.auth_token = None
        settings.security.api_keys_enabled = True
        settings.security.api_key_secret = "test-secret-key-32-chars-long!!"
        settings.auth.storage.api_keys_file = tmp_path / "api_keys.json"
        return settings

    @pytest.mark.asyncio
    async def test_valid_api_key_authenticates(
        self, mock_settings: MagicMock, tmp_path: Path
    ) -> None:
        """Test that a valid API key token authenticates successfully."""
        from claude_code_proxy.auth.api_keys import APIKeyCreate, APIKeyManager

        # Create a valid key
        manager = APIKeyManager(
            storage_path=tmp_path / "api_keys.json",
            secret_key="test-secret-key-32-chars-long!!",
        )
        _, token = manager.create_key(APIKeyCreate(user_id="john", expires_days=90))

        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        with patch(
            "claude_code_proxy.auth.dependencies.get_api_key_manager"
        ) as mock_get_manager:
            mock_get_manager.return_value = manager

            auth_manager = await _get_auth_manager_with_settings(
                credentials, mock_settings
            )

            assert await auth_manager.is_authenticated()
