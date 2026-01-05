# tests/unit/config/test_api_key_config.py
"""Tests for API key configuration."""

import os
from pathlib import Path

import pytest

from claude_code_proxy.config.security import SecuritySettings


class TestAPIKeyConfig:
    """Tests for API key configuration settings."""

    def test_api_key_secret_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test loading API key secret from environment."""
        monkeypatch.setenv("CCPROXY_API_KEY_SECRET", "my-32-char-secret-key-for-jwt!!")

        settings = SecuritySettings()

        assert settings.api_key_secret == "my-32-char-secret-key-for-jwt!!"

    def test_api_key_secret_auto_generated(self) -> None:
        """Test API key secret is auto-generated if not set and API keys enabled."""
        settings = SecuritySettings(api_keys_enabled=True)

        # Should have a secret (auto-generated when enabled)
        assert settings.api_key_secret is not None
        assert settings.api_key_secret_generated is True

    def test_api_keys_enabled_default(self) -> None:
        """Test API keys are disabled by default."""
        settings = SecuritySettings()

        assert settings.api_keys_enabled is False
