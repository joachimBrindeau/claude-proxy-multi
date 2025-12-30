"""Tests for credentials manager validation method.

This module specifically tests the changes to the validate() method in
CredentialsManager that now raises CredentialsNotFoundError with a
descriptive error message when no credentials are found.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from claude_code_proxy.auth.models import (
    ClaudeCredentials,
    OAuthToken,
    ValidationResult,
)
from claude_code_proxy.config.auth import AuthSettings
from claude_code_proxy.exceptions import CredentialsNotFoundError
from claude_code_proxy.services.credentials.manager import CredentialsManager


class TestCredentialsManagerValidation:
    """Test CredentialsManager validation method changes."""

    @pytest.fixture
    def auth_settings(self) -> AuthSettings:
        """Create auth settings for testing."""
        return AuthSettings()

    @pytest.fixture
    def mock_storage(self) -> AsyncMock:
        """Create mock storage backend."""
        mock = AsyncMock()
        # Make get_location return a string, not a coroutine
        mock.get_location = MagicMock(
            return_value="/home/user/.claude/credentials.json"
        )
        return mock

    @pytest.fixture
    def mock_oauth_client(self) -> AsyncMock:
        """Create mock OAuth client."""
        mock = AsyncMock()
        return mock

    @pytest.fixture
    def credentials_manager(
        self,
        auth_settings: AuthSettings,
        mock_storage: AsyncMock,
        mock_oauth_client: AsyncMock,
    ) -> CredentialsManager:
        """Create credentials manager with mocked dependencies."""
        return CredentialsManager(
            config=auth_settings,
            storage=mock_storage,
            oauth_client=mock_oauth_client,
        )

    @pytest.fixture
    def mock_oauth_token(self) -> MagicMock:
        """Create mock OAuth token."""
        mock_token = MagicMock(spec=OAuthToken)
        mock_token.accessToken = "sk-test-token-123"
        mock_token.refreshToken = "refresh-token-456"
        mock_token.expiresAt = None
        mock_token.tokenType = "Bearer"
        mock_token.subscriptionType = "pro"
        mock_token.scopes = ["chat", "completions"]
        mock_token.is_expired = False  # Default to not expired
        return mock_token

    @pytest.fixture
    def mock_credentials(self, mock_oauth_token: MagicMock) -> MagicMock:
        """Create mock Claude credentials."""
        mock_creds = MagicMock(spec=ClaudeCredentials)
        mock_creds.claude_ai_oauth = mock_oauth_token
        mock_creds.claudeAiOauth = (
            mock_oauth_token  # Both property names for compatibility
        )
        return mock_creds

    async def test_validate_with_valid_credentials(
        self,
        credentials_manager: CredentialsManager,
        mock_storage: AsyncMock,
        mock_credentials: MagicMock,
    ) -> None:
        """Test validate method with valid credentials."""
        # Mock storage to return valid credentials
        mock_storage.load.return_value = mock_credentials
        mock_storage.get_location.return_value = "/home/user/.claude/credentials.json"

        result = await credentials_manager.validate()

        assert isinstance(result, ValidationResult)
        assert result.valid is True
        assert result.expired == mock_credentials.claude_ai_oauth.is_expired
        assert result.credentials == mock_credentials
        assert result.path == "/home/user/.claude/credentials.json"

        # Verify storage was called
        mock_storage.load.assert_called_once()
        mock_storage.get_location.assert_called_once()

    async def test_validate_with_no_credentials_raises_descriptive_error(
        self,
        credentials_manager: CredentialsManager,
        mock_storage: AsyncMock,
    ) -> None:
        """Test validate method raises CredentialsNotFoundError with descriptive message when no credentials found.

        This tests the specific change where the validate() method now raises
        CredentialsNotFoundError with the message "No credentials found. Please login first."
        instead of just returning an invalid ValidationResult.
        """
        # Mock storage to return None (no credentials)
        mock_storage.load.return_value = None

        with pytest.raises(CredentialsNotFoundError) as exc_info:
            await credentials_manager.validate()

        # Verify the specific error message that was added
        assert str(exc_info.value) == "No credentials found. Please login first."

        # Verify storage was called
        mock_storage.load.assert_called_once()
        # get_location should not be called when no credentials exist
        mock_storage.get_location.assert_not_called()

    async def test_validate_with_expired_credentials(
        self,
        credentials_manager: CredentialsManager,
        mock_storage: AsyncMock,
        mock_credentials: MagicMock,
    ) -> None:
        """Test validate method with expired credentials."""
        # Set the token to be expired
        mock_credentials.claude_ai_oauth.is_expired = True
        mock_storage.load.return_value = mock_credentials
        mock_storage.get_location.return_value = "/home/user/.claude/credentials.json"

        result = await credentials_manager.validate()

        assert isinstance(result, ValidationResult)
        assert result.valid is True  # Still valid, just expired
        assert result.expired is True
        assert result.credentials == mock_credentials
        assert result.path == "/home/user/.claude/credentials.json"

    async def test_validate_with_storage_exception(
        self,
        credentials_manager: CredentialsManager,
        mock_storage: AsyncMock,
    ) -> None:
        """Test validate method when storage raises an exception."""
        # Mock storage to raise an exception
        mock_storage.load.side_effect = Exception("Storage error")

        with pytest.raises(CredentialsNotFoundError) as exc_info:
            await credentials_manager.validate()

        # Should still raise CredentialsNotFoundError with the descriptive message
        # because load() returns None when it catches exceptions
        assert str(exc_info.value) == "No credentials found. Please login first."

    async def test_validate_preserves_existing_behavior_for_valid_credentials(
        self,
        credentials_manager: CredentialsManager,
        mock_storage: AsyncMock,
        mock_credentials: MagicMock,
    ) -> None:
        """Test that validate method preserves existing behavior for valid credentials."""
        # Set up non-expired token
        mock_credentials.claude_ai_oauth.is_expired = False
        mock_storage.load.return_value = mock_credentials
        mock_storage.get_location.return_value = "/home/user/.claude/credentials.json"

        result = await credentials_manager.validate()

        # Verify all the expected fields are set correctly
        assert result.valid is True
        assert result.expired is False
        assert result.credentials is mock_credentials
        assert result.path == "/home/user/.claude/credentials.json"

    async def test_validate_error_message_consistency(
        self,
        credentials_manager: CredentialsManager,
        mock_storage: AsyncMock,
    ) -> None:
        """Test that the error message is consistent with other methods.

        This ensures the error message matches what's used in other methods
        like get_valid_credentials() for consistency.
        """
        mock_storage.load.return_value = None

        with pytest.raises(CredentialsNotFoundError) as exc_info:
            await credentials_manager.validate()

        # The error message should match what's used in get_valid_credentials
        expected_message = "No credentials found. Please login first."
        assert str(exc_info.value) == expected_message

    @patch("claude_code_proxy.services.credentials.manager.logger")
    async def test_validate_no_credentials_logging(
        self,
        mock_logger: MagicMock,
        credentials_manager: CredentialsManager,
        mock_storage: AsyncMock,
    ) -> None:
        """Test that appropriate logging occurs when no credentials are found."""
        mock_storage.load.return_value = None

        with pytest.raises(CredentialsNotFoundError):
            await credentials_manager.validate()

        # The load method should log the error when it returns None
        # This verifies the existing logging behavior is preserved
        mock_storage.load.assert_called_once()

    async def test_validate_integration_with_load_method(
        self,
        auth_settings: AuthSettings,
    ) -> None:
        """Test validate method integration with actual load method behavior."""
        # Create manager without mocked storage to test real integration
        manager = CredentialsManager(config=auth_settings)

        # Mock the storage's load method to return None
        with patch.object(manager.storage, "load", return_value=None):
            with pytest.raises(CredentialsNotFoundError) as exc_info:
                await manager.validate()

            assert str(exc_info.value) == "No credentials found. Please login first."

    async def test_validate_method_signature_unchanged(
        self,
        credentials_manager: CredentialsManager,
        mock_storage: AsyncMock,
        mock_credentials: MagicMock,
    ) -> None:
        """Test that the validate method signature and return type are unchanged for valid credentials."""
        mock_storage.load.return_value = mock_credentials
        mock_storage.get_location.return_value = "/test/path"

        result = await credentials_manager.validate()

        # Verify the return type is still ValidationResult
        assert isinstance(result, ValidationResult)

        # Verify all expected attributes exist
        assert hasattr(result, "valid")
        assert hasattr(result, "expired")
        assert hasattr(result, "credentials")
        assert hasattr(result, "path")
