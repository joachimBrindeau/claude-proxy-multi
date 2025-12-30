"""Tests for CLI auth login command credentials handling.

This module specifically tests the new CredentialsNotFoundError handling
in the login command that was added to handle cases where no credentials
exist during the login process.
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

from claude_code_proxy.auth.models import (
    ClaudeCredentials,
    OAuthToken,
    ValidationResult,
)
from claude_code_proxy.cli.commands.auth import app
from claude_code_proxy.exceptions import CredentialsNotFoundError
from claude_code_proxy.services.credentials.manager import CredentialsManager


class TestLoginCommandCredentialsHandling:
    """Test login command credentials handling for CredentialsNotFoundError."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create CLI test runner."""
        return CliRunner(env={"NO_COLOR": "1"})

    @pytest.fixture
    def mock_credentials_manager(self) -> AsyncMock:
        """Create mock credentials manager."""
        mock = AsyncMock(spec=CredentialsManager)
        return mock

    @pytest.fixture
    def mock_oauth_token(self) -> OAuthToken:
        """Create mock OAuth token."""
        return OAuthToken(
            accessToken="sk-test-token-123",
            refreshToken="refresh-token-456",
            expiresAt=None,
            tokenType="Bearer",
            subscriptionType="pro",
            scopes=["chat", "completions"],
        )

    @pytest.fixture
    def mock_credentials(self, mock_oauth_token: OAuthToken) -> ClaudeCredentials:
        """Create mock Claude credentials."""
        return ClaudeCredentials(claudeAiOauth=mock_oauth_token)

    @pytest.fixture
    def mock_validation_result_valid(
        self, mock_credentials: ClaudeCredentials
    ) -> ValidationResult:
        """Create valid validation result."""
        return ValidationResult(
            valid=True,
            expired=False,
            path="/home/user/.claude/credentials.json",
            credentials=mock_credentials,
        )

    @pytest.fixture
    def mock_validation_result_invalid(self) -> ValidationResult:
        """Create invalid validation result."""
        return ValidationResult(
            valid=False,
            expired=False,
            path=None,
            credentials=None,
        )

    @patch("ccproxy.cli.commands.auth.get_credentials_manager")
    def test_login_command_no_existing_credentials(
        self,
        mock_get_manager: MagicMock,
        runner: CliRunner,
        mock_credentials_manager: AsyncMock,
        mock_validation_result_valid: ValidationResult,
    ) -> None:
        """Test login command when no existing credentials are found.

        This tests the new CredentialsNotFoundError handling that was added
        to allow login to proceed when no credentials exist.
        """
        mock_get_manager.return_value = mock_credentials_manager

        # First validate() call raises CredentialsNotFoundError (no existing credentials)
        # Second validate() call returns valid result (after successful login)
        mock_credentials_manager.validate.side_effect = [
            CredentialsNotFoundError("No credentials found. Please login first."),
            mock_validation_result_valid,
        ]
        mock_credentials_manager.login.return_value = None

        result = runner.invoke(app, ["login"])

        assert result.exit_code == 0
        assert "Successfully logged in to Claude!" in result.stdout

        # Verify that login was called despite the CredentialsNotFoundError
        mock_credentials_manager.login.assert_called_once()

        # Verify that validate was called twice (once for check, once for final validation)
        assert mock_credentials_manager.validate.call_count == 2

    @patch("ccproxy.cli.commands.auth.get_credentials_manager")
    def test_login_command_credentials_not_found_then_login_success(
        self,
        mock_get_manager: MagicMock,
        runner: CliRunner,
        mock_credentials_manager: AsyncMock,
        mock_validation_result_valid: ValidationResult,
    ) -> None:
        """Test login flow when CredentialsNotFoundError is raised initially.

        This specifically tests that the try-catch block around manager.validate()
        properly handles CredentialsNotFoundError and allows login to proceed.
        """
        mock_get_manager.return_value = mock_credentials_manager

        # Mock the sequence: no credentials found -> login succeeds -> validation succeeds
        mock_credentials_manager.validate.side_effect = [
            CredentialsNotFoundError("No credentials found. Please login first."),
            mock_validation_result_valid,
        ]
        mock_credentials_manager.login.return_value = None

        result = runner.invoke(app, ["login"])

        assert result.exit_code == 0
        assert "Starting OAuth login process..." in result.stdout
        assert "Successfully logged in to Claude!" in result.stdout

        # Should not show the "already logged in" message
        assert "You are already logged in with valid credentials" not in result.stdout

        # Verify login was attempted
        mock_credentials_manager.login.assert_called_once()

    @patch("ccproxy.cli.commands.auth.get_credentials_manager")
    def test_login_command_existing_valid_credentials_overwrite_yes(
        self,
        mock_get_manager: MagicMock,
        runner: CliRunner,
        mock_credentials_manager: AsyncMock,
        mock_validation_result_valid: ValidationResult,
    ) -> None:
        """Test login command with existing valid credentials and user chooses to overwrite."""
        mock_get_manager.return_value = mock_credentials_manager

        # First validate() returns valid credentials (already logged in)
        # Second validate() returns valid result (after re-login)
        mock_credentials_manager.validate.side_effect = [
            mock_validation_result_valid,
            mock_validation_result_valid,
        ]
        mock_credentials_manager.login.return_value = None

        # Simulate user saying "yes" to overwrite
        result = runner.invoke(app, ["login"], input="y\n")

        assert result.exit_code == 0
        assert "You are already logged in with valid credentials" in result.stdout
        assert (
            "Do you want to login again and overwrite existing credentials?"
            in result.stdout
        )
        assert "Successfully logged in to Claude!" in result.stdout

        # Verify login was called after user confirmed overwrite
        mock_credentials_manager.login.assert_called_once()

    @patch("ccproxy.cli.commands.auth.get_credentials_manager")
    def test_login_command_existing_valid_credentials_overwrite_no(
        self,
        mock_get_manager: MagicMock,
        runner: CliRunner,
        mock_credentials_manager: AsyncMock,
        mock_validation_result_valid: ValidationResult,
    ) -> None:
        """Test login command with existing valid credentials and user chooses not to overwrite."""
        mock_get_manager.return_value = mock_credentials_manager
        mock_credentials_manager.validate.return_value = mock_validation_result_valid

        # Simulate user saying "no" to overwrite
        result = runner.invoke(app, ["login"], input="n\n")

        assert result.exit_code == 0
        assert "You are already logged in with valid credentials" in result.stdout
        assert "Login cancelled" in result.stdout

        # Verify login was NOT called
        mock_credentials_manager.login.assert_not_called()

    @patch("ccproxy.cli.commands.auth.get_credentials_manager")
    def test_login_command_credentials_not_found_with_docker_flag(
        self,
        mock_get_manager: MagicMock,
        runner: CliRunner,
        mock_credentials_manager: AsyncMock,
        mock_validation_result_valid: ValidationResult,
    ) -> None:
        """Test login command with --docker flag when no credentials exist."""
        mock_get_manager.return_value = mock_credentials_manager

        # CredentialsNotFoundError on first check, then successful login
        mock_credentials_manager.validate.side_effect = [
            CredentialsNotFoundError("No credentials found. Please login first."),
            mock_validation_result_valid,
        ]
        mock_credentials_manager.login.return_value = None

        result = runner.invoke(app, ["login", "--docker"])

        assert result.exit_code == 0
        assert "Successfully logged in to Claude!" in result.stdout

        # Verify that get_credentials_manager was called with Docker paths
        mock_get_manager.assert_called_once()
        call_args = mock_get_manager.call_args
        if len(call_args[0]) > 0:
            custom_paths = call_args[0][0]
        else:
            custom_paths = call_args.kwargs.get("custom_paths")
        assert custom_paths is not None
        assert any(".claude" in str(path) for path in custom_paths)

    @patch("ccproxy.cli.commands.auth.get_credentials_manager")
    def test_login_command_credentials_not_found_with_custom_file(
        self,
        mock_get_manager: MagicMock,
        runner: CliRunner,
        mock_credentials_manager: AsyncMock,
        mock_validation_result_valid: ValidationResult,
    ) -> None:
        """Test login command with --credential-file flag when no credentials exist."""
        mock_get_manager.return_value = mock_credentials_manager

        # CredentialsNotFoundError on first check, then successful login
        mock_credentials_manager.validate.side_effect = [
            CredentialsNotFoundError("No credentials found. Please login first."),
            mock_validation_result_valid,
        ]
        mock_credentials_manager.login.return_value = None
        custom_file = "/custom/credentials.json"

        result = runner.invoke(app, ["login", "--credential-file", custom_file])

        assert result.exit_code == 0
        assert "Successfully logged in to Claude!" in result.stdout

        # Verify that get_credentials_manager was called with custom file path
        mock_get_manager.assert_called_once()
        call_args = mock_get_manager.call_args
        if len(call_args[0]) > 0:
            custom_paths = call_args[0][0]
        else:
            custom_paths = call_args.kwargs.get("custom_paths")
        assert custom_paths == [Path(custom_file)]

    @patch("ccproxy.cli.commands.auth.get_credentials_manager")
    def test_login_command_other_exception_during_validation(
        self,
        mock_get_manager: MagicMock,
        runner: CliRunner,
        mock_credentials_manager: AsyncMock,
    ) -> None:
        """Test that other exceptions during validation are not caught by the CredentialsNotFoundError handler."""
        mock_get_manager.return_value = mock_credentials_manager

        # Some other exception that should not be caught
        mock_credentials_manager.validate.side_effect = RuntimeError("Some other error")

        result = runner.invoke(app, ["login"])

        # Should exit with error code due to unhandled exception
        assert result.exit_code == 1
        assert "Error during login: Some other error" in result.stdout

        # Login should not be called due to the exception
        mock_credentials_manager.login.assert_not_called()

    @patch("ccproxy.cli.commands.auth.get_credentials_manager")
    def test_login_command_login_fails_after_credentials_not_found(
        self,
        mock_get_manager: MagicMock,
        runner: CliRunner,
        mock_credentials_manager: AsyncMock,
    ) -> None:
        """Test login command when login fails after CredentialsNotFoundError."""
        mock_get_manager.return_value = mock_credentials_manager

        # No existing credentials, but login fails
        mock_credentials_manager.validate.side_effect = CredentialsNotFoundError(
            "No credentials found. Please login first."
        )
        mock_credentials_manager.login.side_effect = Exception("Login failed")

        result = runner.invoke(app, ["login"])

        assert result.exit_code == 1
        assert "Login failed. Please try again." in result.stdout

        # Verify login was attempted
        mock_credentials_manager.login.assert_called_once()
