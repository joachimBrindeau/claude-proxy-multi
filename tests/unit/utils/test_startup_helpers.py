"""Tests for startup utility functions.

This module tests the startup helper functions extracted from the lifespan function:
- Authentication validation
- Claude CLI checking
- Service initialization (detection, SDK, scheduler, storage, permissions)
- Graceful degradation and error handling
- Component lifecycle management

All tests use mocks to avoid external dependencies and test in isolation.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import FastAPI

from ccproxy.auth.exceptions import CredentialsNotFoundError
from ccproxy.config.settings import Settings
from ccproxy.scheduler.errors import SchedulerError
from ccproxy.utils.startup_helpers import (
    check_claude_cli_startup,
    flush_streaming_batches_shutdown,
    initialize_claude_detection_startup,
    initialize_claude_sdk_startup,
    initialize_permission_service_startup,
    setup_permission_service_shutdown,
    setup_scheduler_shutdown,
    setup_scheduler_startup,
    setup_session_manager_shutdown,
    validate_claude_authentication_startup,
)


class TestValidateAuthenticationStartup:
    """Test authentication validation during startup."""

    @pytest.fixture
    def mock_app(self) -> FastAPI:
        """Create a mock FastAPI app."""
        return FastAPI()

    @pytest.fixture
    def mock_settings(self) -> Mock:
        """Create mock settings."""
        settings = Mock(spec=Settings)
        # Configure nested attributes properly
        settings.auth = Mock()
        settings.auth.storage = Mock()
        settings.auth.storage.storage_paths = ["/path1", "/path2"]
        return settings

    @pytest.fixture
    def mock_credentials_manager(self) -> Mock:
        """Create mock credentials manager."""
        return AsyncMock()

    async def test_valid_authentication_with_oauth_token(
        self, mock_app: FastAPI, mock_settings: Mock
    ) -> None:
        """Test successful authentication validation with OAuth token."""
        with patch(
            "ccproxy.utils.startup_helpers.CredentialsManager"
        ) as MockCredentialsManager:
            # Setup mock validation response
            mock_validation = Mock()
            mock_validation.valid = True
            mock_validation.expired = False
            mock_validation.path = "/mock/path"

            # Setup mock credentials with OAuth token
            mock_oauth_token = Mock()
            mock_oauth_token.expires_at_datetime = datetime.now(UTC) + timedelta(
                hours=24
            )
            mock_oauth_token.subscription_type = "pro"

            mock_credentials = Mock()
            mock_credentials.claude_ai_oauth = mock_oauth_token
            mock_validation.credentials = mock_credentials

            mock_manager = AsyncMock()
            mock_manager.validate.return_value = mock_validation
            MockCredentialsManager.return_value = mock_manager

            with patch("ccproxy.utils.startup_helpers.logger") as mock_logger:
                await validate_claude_authentication_startup(mock_app, mock_settings)

                # Verify credentials manager was created and validated
                MockCredentialsManager.assert_called_once()
                mock_manager.validate.assert_called_once()

                # Verify debug log was called with OAuth info
                mock_logger.debug.assert_called_once()
                call_args = mock_logger.debug.call_args[1]
                assert "claude_token_valid" in mock_logger.debug.call_args[0]
                assert "expires_in_hours" in call_args
                assert "subscription_type" in call_args

    async def test_valid_authentication_without_oauth_token(
        self, mock_app: FastAPI, mock_settings: Mock
    ) -> None:
        """Test successful authentication validation without OAuth token."""
        with patch(
            "ccproxy.utils.startup_helpers.CredentialsManager"
        ) as MockCredentialsManager:
            # Setup mock validation response without OAuth
            mock_validation = Mock()
            mock_validation.valid = True
            mock_validation.expired = False
            mock_validation.path = "/mock/path"
            mock_validation.credentials = None

            mock_manager = AsyncMock()
            mock_manager.validate.return_value = mock_validation
            MockCredentialsManager.return_value = mock_manager

            with patch("ccproxy.utils.startup_helpers.logger") as mock_logger:
                await validate_claude_authentication_startup(mock_app, mock_settings)

                # Verify debug log was called without OAuth info
                mock_logger.debug.assert_called_once_with(
                    "claude_token_valid", credentials_path="/mock/path"
                )

    async def test_expired_authentication(
        self, mock_app: FastAPI, mock_settings: Mock
    ) -> None:
        """Test handling of expired authentication."""
        with patch(
            "ccproxy.utils.startup_helpers.CredentialsManager"
        ) as MockCredentialsManager:
            # Setup expired validation response
            mock_validation = Mock()
            mock_validation.valid = False
            mock_validation.expired = True
            mock_validation.path = "/mock/path"

            mock_manager = AsyncMock()
            mock_manager.validate.return_value = mock_validation
            MockCredentialsManager.return_value = mock_manager

            with patch("ccproxy.utils.startup_helpers.logger") as mock_logger:
                await validate_claude_authentication_startup(mock_app, mock_settings)

                # Verify warning was logged
                mock_logger.warning.assert_called_once()
                call_args = mock_logger.warning.call_args[1]
                assert "claude_token_expired" in mock_logger.warning.call_args[0]
                assert "credentials_path" in call_args

    async def test_invalid_authentication(
        self, mock_app: FastAPI, mock_settings: Mock
    ) -> None:
        """Test handling of invalid authentication."""
        with patch(
            "ccproxy.utils.startup_helpers.CredentialsManager"
        ) as MockCredentialsManager:
            # Setup invalid validation response
            mock_validation = Mock()
            mock_validation.valid = False
            mock_validation.expired = False
            mock_validation.path = "/mock/path"

            mock_manager = AsyncMock()
            mock_manager.validate.return_value = mock_validation
            MockCredentialsManager.return_value = mock_manager

            with patch("ccproxy.utils.startup_helpers.logger") as mock_logger:
                await validate_claude_authentication_startup(mock_app, mock_settings)

                # Verify warning was logged
                mock_logger.warning.assert_called_once()
                call_args = mock_logger.warning.call_args[1]
                assert "claude_token_invalid" in mock_logger.warning.call_args[0]

    async def test_credentials_not_found(
        self, mock_app: FastAPI, mock_settings: Mock
    ) -> None:
        """Test handling when credentials are not found."""
        with patch(
            "ccproxy.utils.startup_helpers.CredentialsManager"
        ) as MockCredentialsManager:
            mock_manager = AsyncMock()
            mock_manager.validate.side_effect = CredentialsNotFoundError("Not found")
            MockCredentialsManager.return_value = mock_manager

            with patch("ccproxy.utils.startup_helpers.logger") as mock_logger:
                await validate_claude_authentication_startup(mock_app, mock_settings)

                # Verify warning was logged with searched paths
                mock_logger.warning.assert_called_once()
                call_args = mock_logger.warning.call_args[1]
                assert "claude_token_not_found" in mock_logger.warning.call_args[0]
                assert call_args["searched_paths"] == ["/path1", "/path2"]

    async def test_authentication_validation_error(
        self, mock_app: FastAPI, mock_settings: Mock
    ) -> None:
        """Test handling of unexpected errors during validation."""
        with patch(
            "ccproxy.utils.startup_helpers.CredentialsManager"
        ) as MockCredentialsManager:
            mock_manager = AsyncMock()
            mock_manager.validate.side_effect = Exception("Unexpected error")
            MockCredentialsManager.return_value = mock_manager

            with patch("ccproxy.utils.startup_helpers.logger") as mock_logger:
                await validate_claude_authentication_startup(mock_app, mock_settings)

                # Verify error was logged
                mock_logger.error.assert_called_once()
                call_args = mock_logger.error.call_args[1]
                assert "claude_token_validation_error" in mock_logger.error.call_args[0]
                assert call_args["error"] == "Unexpected error"
                assert call_args["exc_info"] is True


class TestCheckClaudeCLIStartup:
    """Test Claude CLI checking during startup."""

    @pytest.fixture
    def mock_app(self) -> FastAPI:
        """Create a mock FastAPI app."""
        return FastAPI()

    @pytest.fixture
    def mock_settings(self) -> Mock:
        """Create mock settings."""
        return Mock(spec=Settings)

    async def test_claude_cli_available(
        self, mock_app: FastAPI, mock_settings: Mock
    ) -> None:
        """Test successful Claude CLI detection."""
        with patch("ccproxy.api.routes.health.get_claude_cli_info") as mock_get_info:
            # Setup mock CLI info response
            mock_info = Mock()
            mock_info.status = "available"
            mock_info.version = "1.2.3"
            mock_info.binary_path = "/usr/local/bin/claude"
            mock_get_info.return_value = mock_info

            with patch("ccproxy.utils.startup_helpers.logger") as mock_logger:
                await check_claude_cli_startup(mock_app, mock_settings)

                # Verify info log was called
                mock_logger.info.assert_called_once()
                call_args = mock_logger.info.call_args[1]
                assert "claude_cli_available" in mock_logger.info.call_args[0]
                assert call_args["status"] == "available"
                assert call_args["version"] == "1.2.3"
                assert call_args["binary_path"] == "/usr/local/bin/claude"

    async def test_claude_cli_unavailable(
        self, mock_app: FastAPI, mock_settings: Mock
    ) -> None:
        """Test handling when Claude CLI is unavailable."""
        with patch("ccproxy.api.routes.health.get_claude_cli_info") as mock_get_info:
            # Setup mock CLI info response for unavailable
            mock_info = Mock()
            mock_info.status = "not_found"
            mock_info.error = "Claude CLI not found in PATH"
            mock_info.binary_path = None
            mock_get_info.return_value = mock_info

            with patch("ccproxy.utils.startup_helpers.logger") as mock_logger:
                await check_claude_cli_startup(mock_app, mock_settings)

                # Verify warning log was called
                mock_logger.warning.assert_called_once()
                call_args = mock_logger.warning.call_args[1]
                assert "claude_cli_unavailable" in mock_logger.warning.call_args[0]
                assert call_args["status"] == "not_found"
                assert call_args["error"] == "Claude CLI not found in PATH"

    async def test_claude_cli_check_error(
        self, mock_app: FastAPI, mock_settings: Mock
    ) -> None:
        """Test handling of errors during Claude CLI check."""
        with patch("ccproxy.api.routes.health.get_claude_cli_info") as mock_get_info:
            mock_get_info.side_effect = Exception("CLI check failed")

            with patch("ccproxy.utils.startup_helpers.logger") as mock_logger:
                await check_claude_cli_startup(mock_app, mock_settings)

                # Verify error log was called
                mock_logger.error.assert_called_once()
                call_args = mock_logger.error.call_args[1]
                assert "claude_cli_check_failed" in mock_logger.error.call_args[0]
                assert call_args["error"] == "CLI check failed"


class TestSchedulerLifecycle:
    """Test scheduler startup and shutdown."""

    @pytest.fixture
    def mock_app(self) -> FastAPI:
        """Create a mock FastAPI app."""
        app = FastAPI()
        app.state = Mock()
        return app

    @pytest.fixture
    def mock_settings(self) -> Mock:
        """Create mock settings."""
        return Mock(spec=Settings)

    async def test_scheduler_startup_success(
        self, mock_app: FastAPI, mock_settings: Mock
    ) -> None:
        """Test successful scheduler startup."""
        # Ensure no session_manager exists to avoid task addition
        if hasattr(mock_app.state, "session_manager"):
            delattr(mock_app.state, "session_manager")

        with patch("ccproxy.utils.startup_helpers.start_scheduler") as mock_start:
            mock_scheduler = AsyncMock()
            mock_start.return_value = mock_scheduler

            with patch("ccproxy.utils.startup_helpers.logger") as mock_logger:
                await setup_scheduler_startup(mock_app, mock_settings)

                # Verify scheduler was started and stored
                mock_start.assert_called_once_with(mock_settings)
                assert mock_app.state.scheduler == mock_scheduler

                # Verify debug log was called
                mock_logger.debug.assert_called_with("scheduler_initialized")

    async def test_scheduler_startup_with_session_manager(
        self, mock_app: FastAPI, mock_settings: Mock
    ) -> None:
        """Test scheduler startup with session manager for task addition."""
        mock_session_manager = AsyncMock()
        mock_app.state.session_manager = mock_session_manager

        with patch("ccproxy.utils.startup_helpers.start_scheduler") as mock_start:
            mock_scheduler = AsyncMock()
            mock_start.return_value = mock_scheduler

            with patch("ccproxy.utils.startup_helpers.logger") as mock_logger:
                await setup_scheduler_startup(mock_app, mock_settings)

                # Verify task was added to scheduler
                mock_scheduler.add_task.assert_called_once()
                task_args = mock_scheduler.add_task.call_args[1]
                assert task_args["task_name"] == "session_pool_stats"
                assert task_args["task_type"] == "pool_stats"
                assert task_args["interval_seconds"] == 60
                assert task_args["pool_manager"] == mock_session_manager

    async def test_scheduler_startup_error(
        self, mock_app: FastAPI, mock_settings: Mock
    ) -> None:
        """Test error handling during scheduler startup."""
        with patch("ccproxy.utils.startup_helpers.start_scheduler") as mock_start:
            mock_start.side_effect = SchedulerError("Scheduler start failed")

            with patch("ccproxy.utils.startup_helpers.logger") as mock_logger:
                await setup_scheduler_startup(mock_app, mock_settings)

                # Verify error was logged
                mock_logger.error.assert_called_once()
                call_args = mock_logger.error.call_args[1]
                assert (
                    "scheduler_initialization_failed" in mock_logger.error.call_args[0]
                )
                assert call_args["error"] == "Scheduler start failed"

    async def test_scheduler_shutdown_success(self, mock_app: FastAPI) -> None:
        """Test successful scheduler shutdown."""
        mock_scheduler = AsyncMock()
        mock_app.state.scheduler = mock_scheduler

        with (
            patch("ccproxy.utils.startup_helpers.stop_scheduler") as mock_stop,
            patch("ccproxy.utils.startup_helpers.logger") as mock_logger,
        ):
            await setup_scheduler_shutdown(mock_app)

            # Verify scheduler was stopped
            mock_stop.assert_called_once_with(mock_scheduler)

            # Verify debug log was called
            mock_logger.debug.assert_called_once_with("scheduler_stopped_lifespan")

    async def test_scheduler_shutdown_error(self, mock_app: FastAPI) -> None:
        """Test error handling during scheduler shutdown."""
        mock_scheduler = AsyncMock()
        mock_app.state.scheduler = mock_scheduler

        with patch("ccproxy.utils.startup_helpers.stop_scheduler") as mock_stop:
            mock_stop.side_effect = SchedulerError("Stop failed")

            with patch("ccproxy.utils.startup_helpers.logger") as mock_logger:
                await setup_scheduler_shutdown(mock_app)

                # Verify error was logged
                mock_logger.error.assert_called_once()
                call_args = mock_logger.error.call_args[1]
                assert "scheduler_stop_failed" in mock_logger.error.call_args[0]
                assert call_args["error"] == "Stop failed"


class TestSessionManagerShutdown:
    """Test session manager shutdown."""

    @pytest.fixture
    def mock_app(self) -> FastAPI:
        """Create a mock FastAPI app."""
        app = FastAPI()
        app.state = Mock()
        return app

    async def test_session_manager_shutdown_success(self, mock_app: FastAPI) -> None:
        """Test successful session manager shutdown."""
        mock_session_manager = AsyncMock()
        mock_app.state.session_manager = mock_session_manager

        with patch("ccproxy.utils.startup_helpers.logger") as mock_logger:
            await setup_session_manager_shutdown(mock_app)

            # Verify session manager was shut down
            mock_session_manager.shutdown.assert_called_once()

            # Verify debug log was called
            mock_logger.debug.assert_called_once_with(
                "claude_sdk_session_manager_shutdown"
            )

    async def test_session_manager_shutdown_no_manager(self, mock_app: FastAPI) -> None:
        """Test shutdown when no session manager exists."""
        # Ensure no session_manager attribute exists
        if hasattr(mock_app.state, "session_manager"):
            delattr(mock_app.state, "session_manager")

        with patch("ccproxy.utils.startup_helpers.logger") as mock_logger:
            await setup_session_manager_shutdown(mock_app)

            # Verify no logs were called
            mock_logger.debug.assert_not_called()
            mock_logger.error.assert_not_called()

    async def test_session_manager_shutdown_error(self, mock_app: FastAPI) -> None:
        """Test error handling during session manager shutdown."""
        mock_session_manager = AsyncMock()
        mock_session_manager.shutdown.side_effect = Exception("Shutdown failed")
        mock_app.state.session_manager = mock_session_manager

        with patch("ccproxy.utils.startup_helpers.logger") as mock_logger:
            await setup_session_manager_shutdown(mock_app)

            # Verify error was logged
            mock_logger.error.assert_called_once()
            call_args = mock_logger.error.call_args[1]
            assert (
                "claude_sdk_session_manager_shutdown_failed"
                in mock_logger.error.call_args[0]
            )
            assert call_args["error"] == "Shutdown failed"


class TestFlushStreamingBatchesShutdown:
    """Test streaming batches flushing during shutdown."""

    @pytest.fixture
    def mock_app(self) -> FastAPI:
        """Create a mock FastAPI app."""
        return FastAPI()

    async def test_flush_streaming_batches_success(self, mock_app: FastAPI) -> None:
        """Test successful streaming batches flushing."""
        with patch(
            "ccproxy.utils.simple_request_logger.flush_all_streaming_batches"
        ) as mock_flush:
            mock_flush.return_value = None  # Async function returns None

            with patch("ccproxy.utils.startup_helpers.logger") as mock_logger:
                await flush_streaming_batches_shutdown(mock_app)

                # Verify flush function was called
                mock_flush.assert_called_once()

                # Verify debug log was called
                mock_logger.debug.assert_called_once_with("streaming_batches_flushed")

    async def test_flush_streaming_batches_error(self, mock_app: FastAPI) -> None:
        """Test error handling during streaming batches flushing."""
        with patch(
            "ccproxy.utils.simple_request_logger.flush_all_streaming_batches"
        ) as mock_flush:
            mock_flush.side_effect = Exception("Flush failed")

            with patch("ccproxy.utils.startup_helpers.logger") as mock_logger:
                await flush_streaming_batches_shutdown(mock_app)

                # Verify error was logged
                mock_logger.error.assert_called_once()
                call_args = mock_logger.error.call_args[1]
                assert (
                    "streaming_batches_flush_failed" in mock_logger.error.call_args[0]
                )
                assert call_args["error"] == "Flush failed"


class TestClaudeDetectionStartup:
    """Test Claude detection service initialization."""

    @pytest.fixture
    def mock_app(self) -> FastAPI:
        """Create a mock FastAPI app."""
        app = FastAPI()
        app.state = Mock()
        return app

    @pytest.fixture
    def mock_settings(self) -> Mock:
        """Create mock settings."""
        return Mock(spec=Settings)

    async def test_claude_detection_startup_success(
        self, mock_app: FastAPI, mock_settings: Mock
    ) -> None:
        """Test successful Claude detection initialization."""
        with patch(
            "ccproxy.utils.startup_helpers.ClaudeDetectionService"
        ) as MockService:
            mock_service = Mock()
            mock_claude_data = Mock()
            mock_claude_data.claude_version = "1.2.3"
            mock_claude_data.cached_at = datetime.now(UTC)

            mock_service.initialize_detection = AsyncMock(return_value=mock_claude_data)
            MockService.return_value = mock_service

            with patch("ccproxy.utils.startup_helpers.logger") as mock_logger:
                await initialize_claude_detection_startup(mock_app, mock_settings)

                # Verify service was created and initialized
                MockService.assert_called_once_with(mock_settings)
                mock_service.initialize_detection.assert_called_once()

                # Verify data was stored in app state
                assert mock_app.state.claude_detection_data == mock_claude_data
                assert mock_app.state.claude_detection_service == mock_service

    async def test_claude_detection_startup_error_with_fallback(
        self, mock_app: FastAPI, mock_settings: Mock
    ) -> None:
        """Test error handling with fallback during Claude detection."""
        with patch(
            "ccproxy.utils.startup_helpers.ClaudeDetectionService"
        ) as MockService:
            # First service instance fails
            mock_service_failed = Mock()
            mock_service_failed.initialize_detection = AsyncMock(
                side_effect=Exception("Detection failed")
            )

            # Second service instance for fallback
            mock_service_fallback = Mock()
            mock_fallback_data = Mock()
            mock_service_fallback._get_fallback_data.return_value = mock_fallback_data

            MockService.side_effect = [mock_service_failed, mock_service_fallback]

            with patch("ccproxy.utils.startup_helpers.logger") as mock_logger:
                await initialize_claude_detection_startup(mock_app, mock_settings)

                # Verify error was logged
                mock_logger.error.assert_called_once()
                call_args = mock_logger.error.call_args[1]
                assert (
                    "claude_detection_startup_failed" in mock_logger.error.call_args[0]
                )

                # Verify fallback data was used
                assert mock_app.state.claude_detection_data == mock_fallback_data
                assert mock_app.state.claude_detection_service == mock_service_fallback


class TestClaudeSDKStartup:
    """Test Claude SDK service initialization."""

    @pytest.fixture
    def mock_app(self) -> FastAPI:
        """Create a mock FastAPI app."""
        app = FastAPI()
        app.state = Mock()
        return app

    @pytest.fixture
    def mock_settings(self) -> Mock:
        """Create mock settings."""
        settings = Mock(spec=Settings)
        # Configure nested attributes properly
        settings.claude = Mock()
        settings.claude.sdk_session_pool = Mock()
        settings.claude.sdk_session_pool.enabled = True
        return settings

    async def test_claude_sdk_startup_success_with_session_pool(
        self, mock_app: FastAPI, mock_settings: Mock
    ) -> None:
        """Test successful Claude SDK initialization with session pool."""
        with (
            patch(
                "ccproxy.utils.startup_helpers.CredentialsAuthManager"
            ) as MockAuthManager,
            patch("ccproxy.utils.startup_helpers.get_metrics") as mock_get_metrics,
            patch("ccproxy.utils.startup_helpers.ClaudeSDKService") as MockSDKService,
            patch("ccproxy.claude_sdk.manager.SessionManager") as MockSessionManager,
        ):
            # Setup mocks
            mock_auth_manager = Mock()
            MockAuthManager.return_value = mock_auth_manager

            mock_metrics = Mock()
            mock_get_metrics.return_value = mock_metrics

            mock_session_manager = AsyncMock()
            MockSessionManager.return_value = mock_session_manager

            mock_claude_service = Mock()
            MockSDKService.return_value = mock_claude_service

            with patch("ccproxy.utils.startup_helpers.logger") as mock_logger:
                await initialize_claude_sdk_startup(mock_app, mock_settings)

                # Verify session manager was created and started
                MockSessionManager.assert_called_once()
                mock_session_manager.start.assert_called_once()

                # Verify Claude service was created with correct parameters
                MockSDKService.assert_called_once()
                call_kwargs = MockSDKService.call_args[1]
                assert call_kwargs["auth_manager"] == mock_auth_manager
                assert call_kwargs["metrics"] == mock_metrics
                assert call_kwargs["settings"] == mock_settings
                assert call_kwargs["session_manager"] == mock_session_manager

                # Verify services were stored in app state
                assert mock_app.state.claude_service == mock_claude_service
                assert mock_app.state.session_manager == mock_session_manager

    async def test_claude_sdk_startup_without_session_pool(
        self, mock_app: FastAPI, mock_settings: Mock
    ) -> None:
        """Test Claude SDK initialization without session pool."""
        mock_settings.claude.sdk_session_pool.enabled = False

        with (
            patch(
                "ccproxy.utils.startup_helpers.CredentialsAuthManager"
            ) as MockAuthManager,
            patch("ccproxy.utils.startup_helpers.get_metrics") as mock_get_metrics,
            patch("ccproxy.utils.startup_helpers.ClaudeSDKService") as MockSDKService,
        ):
            # Setup mocks
            mock_auth_manager = Mock()
            MockAuthManager.return_value = mock_auth_manager

            mock_metrics = Mock()
            mock_get_metrics.return_value = mock_metrics

            mock_claude_service = Mock()
            MockSDKService.return_value = mock_claude_service

            await initialize_claude_sdk_startup(mock_app, mock_settings)

            # Verify Claude service was created without session manager
            MockSDKService.assert_called_once()
            call_kwargs = MockSDKService.call_args[1]
            assert call_kwargs["session_manager"] is None

    async def test_claude_sdk_startup_error(
        self, mock_app: FastAPI, mock_settings: Mock
    ) -> None:
        """Test error handling during Claude SDK initialization."""
        with patch(
            "ccproxy.utils.startup_helpers.CredentialsAuthManager"
        ) as MockAuthManager:
            MockAuthManager.side_effect = Exception("Auth manager failed")

            with patch("ccproxy.utils.startup_helpers.logger") as mock_logger:
                await initialize_claude_sdk_startup(mock_app, mock_settings)

                # Verify error was logged
                mock_logger.error.assert_called_once()
                call_args = mock_logger.error.call_args[1]
                assert (
                    "claude_sdk_service_initialization_failed"
                    in mock_logger.error.call_args[0]
                )
                assert call_args["error"] == "Auth manager failed"


class TestPermissionServiceLifecycle:
    """Test permission service initialization and shutdown."""

    @pytest.fixture
    def mock_app(self) -> FastAPI:
        """Create a mock FastAPI app."""
        app = FastAPI()
        app.state = Mock()
        return app

    @pytest.fixture
    def mock_settings_enabled(self) -> Mock:
        """Create mock settings with permissions enabled."""
        settings = Mock(spec=Settings)
        # Configure nested attributes properly
        settings.claude = Mock()
        settings.claude.builtin_permissions = True
        settings.server = Mock()
        settings.server.use_terminal_permission_handler = False
        return settings

    @pytest.fixture
    def mock_settings_disabled(self) -> Mock:
        """Create mock settings with permissions disabled."""
        settings = Mock(spec=Settings)
        # Configure nested attributes properly
        settings.claude = Mock()
        settings.claude.builtin_permissions = False
        return settings

    async def test_permission_service_startup_success(
        self, mock_app: FastAPI, mock_settings_enabled: Mock
    ) -> None:
        """Test successful permission service initialization."""
        with patch(
            "ccproxy.api.services.permission_service.get_permission_service"
        ) as mock_get_service:
            mock_permission_service = AsyncMock()
            mock_permission_service._timeout_seconds = 30
            mock_get_service.return_value = mock_permission_service

            with patch("ccproxy.utils.startup_helpers.logger") as mock_logger:
                await initialize_permission_service_startup(
                    mock_app, mock_settings_enabled
                )

                # Verify service was started and stored
                mock_permission_service.start.assert_called_once()
                assert mock_app.state.permission_service == mock_permission_service

    async def test_permission_service_startup_disabled(
        self, mock_app: FastAPI, mock_settings_disabled: Mock
    ) -> None:
        """Test when permission service is disabled."""
        with patch("ccproxy.utils.startup_helpers.logger") as mock_logger:
            await initialize_permission_service_startup(
                mock_app, mock_settings_disabled
            )

            # Verify debug log for skipped service
            mock_logger.debug.assert_called_once()
            call_args = mock_logger.debug.call_args[1]
            assert "permission_service_skipped" in mock_logger.debug.call_args[0]
            assert call_args["builtin_permissions_enabled"] is False

    async def test_permission_service_shutdown_success(
        self, mock_app: FastAPI, mock_settings_enabled: Mock
    ) -> None:
        """Test successful permission service shutdown."""
        mock_permission_service = AsyncMock()
        mock_app.state.permission_service = mock_permission_service

        with patch("ccproxy.utils.startup_helpers.logger") as mock_logger:
            await setup_permission_service_shutdown(mock_app, mock_settings_enabled)

            # Verify service was stopped
            mock_permission_service.stop.assert_called_once()

            # Verify debug log was called
            mock_logger.debug.assert_called_once_with("permission_service_stopped")

    async def test_permission_service_shutdown_disabled(
        self, mock_app: FastAPI, mock_settings_disabled: Mock
    ) -> None:
        """Test shutdown when permission service is disabled."""
        mock_app.state.permission_service = AsyncMock()  # Present but disabled

        with patch("ccproxy.utils.startup_helpers.logger") as mock_logger:
            await setup_permission_service_shutdown(mock_app, mock_settings_disabled)

            # Verify no logs were called (early return due to disabled setting)
            mock_logger.debug.assert_not_called()
            mock_logger.error.assert_not_called()
