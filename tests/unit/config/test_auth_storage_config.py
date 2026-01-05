# tests/unit/config/test_auth_storage_config.py
"""Tests for auth storage configuration."""

from pathlib import Path

import pytest

from claude_code_proxy.config.auth import CredentialStorageSettings


class TestCredentialStorageSettings:
    """Tests for credential storage settings."""

    def test_api_keys_file_default(self) -> None:
        """Test API keys file has sensible default."""
        settings = CredentialStorageSettings()

        assert "api_keys.json" in str(settings.api_keys_file)

    def test_api_keys_file_in_credentials_dir(self) -> None:
        """Test API keys file is in credentials directory."""
        settings = CredentialStorageSettings(credentials_dir=Path("/custom/dir"))

        assert settings.api_keys_file == Path("/custom/dir/api_keys.json")
