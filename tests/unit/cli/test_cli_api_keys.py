# tests/unit/cli/test_cli_api_keys.py
"""Tests for API key management CLI commands."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import typer

from claude_code_proxy.auth.api_keys import APIKeyManager
from claude_code_proxy.cli.commands.api_keys import (
    create_key,
    delete_key,
    get_manager,
    list_keys,
    revoke_key,
)


@pytest.fixture
def temp_api_keys_file(tmp_path):
    """Create a temporary API keys file."""
    keys_file = tmp_path / "api_keys.json"
    keys_file.write_text(json.dumps({"keys": {}, "version": 1}))
    return keys_file


@pytest.fixture
def mock_settings(temp_api_keys_file):
    """Create mock settings with API keys enabled."""
    settings = MagicMock()
    settings.security.api_keys_enabled = True
    settings.security.api_key_secret = "test-secret-key-for-testing-12345"
    settings.auth.storage.api_keys_file = str(temp_api_keys_file)
    return settings


@pytest.fixture
def env_setup(mock_settings, temp_api_keys_file, monkeypatch):
    """Set up environment for API key CLI tests."""
    monkeypatch.setenv("SECURITY__API_KEYS_ENABLED", "true")
    monkeypatch.setenv("SECURITY__API_KEY_SECRET", "test-secret-key-for-testing-12345")
    monkeypatch.setenv("AUTH__STORAGE__API_KEYS_FILE", str(temp_api_keys_file))
    return mock_settings


class TestGetManager:
    """Tests for get_manager function."""

    def test_get_manager_returns_manager_when_enabled(
        self, env_setup, temp_api_keys_file
    ):
        """Test that get_manager returns APIKeyManager when enabled."""
        with patch("claude_code_proxy.cli.commands.api_keys.get_settings") as mock_get:
            mock_get.return_value = env_setup
            manager = get_manager()
            assert isinstance(manager, APIKeyManager)

    def test_get_manager_exits_when_disabled(self, temp_api_keys_file):
        """Test that get_manager exits when API keys disabled."""
        mock_settings = MagicMock()
        mock_settings.security.api_keys_enabled = False

        with patch("claude_code_proxy.cli.commands.api_keys.get_settings") as mock_get:
            mock_get.return_value = mock_settings
            with pytest.raises(typer.Exit):
                get_manager()

    def test_get_manager_exits_when_no_secret(self, temp_api_keys_file):
        """Test that get_manager exits when no secret configured."""
        mock_settings = MagicMock()
        mock_settings.security.api_keys_enabled = True
        mock_settings.security.api_key_secret = None

        with patch("claude_code_proxy.cli.commands.api_keys.get_settings") as mock_get:
            mock_get.return_value = mock_settings
            with pytest.raises(typer.Exit):
                get_manager()


class TestCreateKey:
    """Tests for create_key command."""

    def test_create_key_success(self, env_setup, temp_api_keys_file):
        """Test successful API key creation."""
        with (
            patch("claude_code_proxy.cli.commands.api_keys.get_settings") as mock_get,
            patch("claude_code_proxy.cli.commands.api_keys.console") as mock_console,
        ):
            mock_get.return_value = env_setup
            create_key(user="test-user", description="Test key", expires_days=30)

            # Verify console.print was called with success message
            assert any(
                "API key created successfully" in str(call)
                for call in mock_console.print.call_args_list
            )

    def test_create_key_with_description(self, env_setup, temp_api_keys_file):
        """Test API key creation with description."""
        with (
            patch("claude_code_proxy.cli.commands.api_keys.get_settings") as mock_get,
            patch("claude_code_proxy.cli.commands.api_keys.console"),
        ):
            mock_get.return_value = env_setup
            create_key(user="test-user", description="My test key", expires_days=90)

            # Verify key was created in storage
            manager = APIKeyManager(
                storage_path=Path(env_setup.auth.storage.api_keys_file),
                secret_key=env_setup.security.api_key_secret,
            )
            keys = manager.list_keys()
            assert len(keys) == 1
            assert keys[0].user_id == "test-user"
            assert keys[0].description == "My test key"


class TestListKeys:
    """Tests for list_keys command."""

    def test_list_keys_empty(self, env_setup, temp_api_keys_file):
        """Test listing keys when none exist."""
        with (
            patch("claude_code_proxy.cli.commands.api_keys.get_settings") as mock_get,
            patch("claude_code_proxy.cli.commands.api_keys.console") as mock_console,
        ):
            mock_get.return_value = env_setup
            list_keys()

            # Verify "No API keys found" was printed
            assert any(
                "No API keys found" in str(call)
                for call in mock_console.print.call_args_list
            )

    def test_list_keys_with_keys(self, env_setup, temp_api_keys_file):
        """Test listing keys when keys exist."""
        with (
            patch("claude_code_proxy.cli.commands.api_keys.get_settings") as mock_get,
            patch("claude_code_proxy.cli.commands.api_keys.console") as mock_console,
        ):
            mock_get.return_value = env_setup
            # First create a key
            create_key(user="test-user", description="Test key", expires_days=30)
            # Reset mock to clear create_key calls
            mock_console.reset_mock()
            # Then list keys
            list_keys()

            # Verify console.print was called with a table
            assert mock_console.print.called


class TestRevokeKey:
    """Tests for revoke_key command."""

    def test_revoke_key_success(self, env_setup, temp_api_keys_file):
        """Test successful key revocation."""
        with (
            patch("claude_code_proxy.cli.commands.api_keys.get_settings") as mock_get,
            patch("claude_code_proxy.cli.commands.api_keys.console") as mock_console,
        ):
            mock_get.return_value = env_setup
            # First create a key
            create_key(user="test-user", description="Test key", expires_days=30)

            # Get the key ID from the manager
            manager = APIKeyManager(
                storage_path=Path(env_setup.auth.storage.api_keys_file),
                secret_key=env_setup.security.api_key_secret,
            )
            keys = manager.list_keys()
            assert len(keys) == 1
            key_id = keys[0].key_id

            # Reset mock to clear create_key calls
            mock_console.reset_mock()

            # Revoke the key
            revoke_key(key_id=key_id)

            # Verify revocation message
            assert any(
                "has been revoked" in str(call)
                for call in mock_console.print.call_args_list
            )

    def test_revoke_key_not_found(self, env_setup, temp_api_keys_file):
        """Test revoking non-existent key."""
        with (
            patch("claude_code_proxy.cli.commands.api_keys.get_settings") as mock_get,
            patch("claude_code_proxy.cli.commands.api_keys.console"),
        ):
            mock_get.return_value = env_setup
            with pytest.raises(typer.Exit):
                revoke_key(key_id="nonexistent-key-id")


class TestDeleteKey:
    """Tests for delete_key command."""

    def test_delete_key_success(self, env_setup, temp_api_keys_file):
        """Test successful key deletion."""
        with (
            patch("claude_code_proxy.cli.commands.api_keys.get_settings") as mock_get,
            patch("claude_code_proxy.cli.commands.api_keys.console") as mock_console,
        ):
            mock_get.return_value = env_setup
            # First create a key
            create_key(user="test-user", description="Test key", expires_days=30)

            # Get the key ID from the manager
            manager = APIKeyManager(
                storage_path=Path(env_setup.auth.storage.api_keys_file),
                secret_key=env_setup.security.api_key_secret,
            )
            keys = manager.list_keys()
            assert len(keys) == 1
            key_id = keys[0].key_id

            # Reset mock to clear create_key calls
            mock_console.reset_mock()

            # Delete the key with force flag
            delete_key(key_id=key_id, force=True)

            # Verify deletion message
            assert any(
                "has been deleted" in str(call)
                for call in mock_console.print.call_args_list
            )

    def test_delete_key_not_found(self, env_setup, temp_api_keys_file):
        """Test deleting non-existent key."""
        with (
            patch("claude_code_proxy.cli.commands.api_keys.get_settings") as mock_get,
            patch("claude_code_proxy.cli.commands.api_keys.console"),
        ):
            mock_get.return_value = env_setup
            with pytest.raises(typer.Exit):
                delete_key(key_id="nonexistent-key-id", force=True)
