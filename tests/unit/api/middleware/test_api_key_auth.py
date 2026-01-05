# tests/unit/api/middleware/test_api_key_auth.py
"""Tests for API key authentication middleware."""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI, status
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from claude_code_proxy.api.middleware.api_key_auth import APIKeyAuthMiddleware
from claude_code_proxy.auth.api_keys import APIKeyCreate, APIKeyManager


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
    settings.security.api_key_secret = "test-secret-key-for-testing-32chars"
    settings.auth.storage.api_keys_file = str(temp_api_keys_file)
    return settings


@pytest.fixture
def mock_settings_disabled(temp_api_keys_file):
    """Create mock settings with API keys disabled."""
    settings = MagicMock()
    settings.security.api_keys_enabled = False
    settings.security.api_key_secret = None
    settings.auth.storage.api_keys_file = str(temp_api_keys_file)
    return settings


@pytest.fixture
def api_key_manager(temp_api_keys_file, mock_settings):
    """Create API key manager for tests."""
    return APIKeyManager(
        storage_path=Path(mock_settings.auth.storage.api_keys_file),
        secret_key=mock_settings.security.api_key_secret,
    )


@pytest.fixture
def app_with_auth(mock_settings):
    """Create FastAPI app with API key auth middleware."""
    app = FastAPI()

    # Add the middleware
    app.add_middleware(APIKeyAuthMiddleware, settings=mock_settings)

    # Add test routes
    @app.get("/")
    async def root():
        return {"message": "root"}

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.get("/api/protected")
    async def protected():
        return {"message": "protected"}

    return app


@pytest.fixture
def app_without_auth(mock_settings_disabled):
    """Create FastAPI app without API key auth (disabled)."""
    app = FastAPI()

    # Add the middleware with disabled settings
    app.add_middleware(APIKeyAuthMiddleware, settings=mock_settings_disabled)

    # Add test routes
    @app.get("/")
    async def root():
        return {"message": "root"}

    @app.get("/api/protected")
    async def protected():
        return {"message": "protected"}

    return app


class TestPublicRoutes:
    """Tests for public routes that don't require authentication."""

    def test_health_endpoint_is_public(self, app_with_auth):
        """Test that /health endpoint is accessible without auth."""
        client = TestClient(app_with_auth)
        response = client.get("/health")
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {"status": "ok"}

    def test_docs_endpoint_is_public(self, app_with_auth):
        """Test that /docs endpoint is accessible without auth."""
        from claude_code_proxy.auth.api_keys import DEFAULT_PUBLIC_ROUTES

        # Test the public routes configuration directly
        assert DEFAULT_PUBLIC_ROUTES.is_public("/docs")
        assert DEFAULT_PUBLIC_ROUTES.is_public("/openapi.json")
        assert DEFAULT_PUBLIC_ROUTES.is_public("/redoc")
        assert DEFAULT_PUBLIC_ROUTES.is_public("/health")


class TestProtectedRoutes:
    """Tests for protected routes that require authentication."""

    def test_protected_route_without_auth_returns_401(self, app_with_auth):
        """Test that protected routes return 401 without auth."""
        client = TestClient(app_with_auth)
        response = client.get("/api/protected")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "error" in response.json()
        assert "Bearer" in response.headers.get("WWW-Authenticate", "")

    def test_protected_route_with_valid_key(
        self, app_with_auth, api_key_manager, mock_settings
    ):
        """Test that protected routes are accessible with valid API key."""
        # Create an API key
        request = APIKeyCreate(
            user_id="test-user", description="Test key", expires_days=30
        )
        _, token = api_key_manager.create_key(request)

        # Make request with the token
        client = TestClient(app_with_auth)
        response = client.get(
            "/api/protected", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {"message": "protected"}

    def test_protected_route_with_invalid_key(self, app_with_auth):
        """Test that protected routes return 401 with invalid API key."""
        client = TestClient(app_with_auth)
        response = client.get(
            "/api/protected", headers={"Authorization": "Bearer invalid-token"}
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        json_response = response.json()
        assert json_response.get("error") == "Invalid API key"
        assert "invalid" in json_response.get("detail", "").lower()

    def test_protected_route_with_revoked_key(
        self, app_with_auth, api_key_manager, mock_settings
    ):
        """Test that revoked keys are rejected."""
        # Create and revoke an API key
        request = APIKeyCreate(
            user_id="test-user", description="Test key", expires_days=30
        )
        key, token = api_key_manager.create_key(request)
        api_key_manager.revoke_key(key.key_id)

        # Make request with the revoked token
        client = TestClient(app_with_auth)
        response = client.get(
            "/api/protected", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestAuthenticationDisabled:
    """Tests for when API key authentication is disabled."""

    def test_all_routes_accessible_when_disabled(self, app_without_auth):
        """Test that all routes are accessible when auth is disabled."""
        client = TestClient(app_without_auth)

        # Root should be accessible
        response = client.get("/")
        assert response.status_code == status.HTTP_200_OK

        # Protected route should also be accessible
        response = client.get("/api/protected")
        assert response.status_code == status.HTTP_200_OK


class TestBearerTokenExtraction:
    """Tests for bearer token extraction logic."""

    def test_extract_valid_bearer_token(self, mock_settings):
        """Test extracting valid bearer token from header."""
        middleware = APIKeyAuthMiddleware(app=MagicMock(), settings=mock_settings)

        request = MagicMock()
        request.headers.get.return_value = "Bearer test-token-123"

        token = middleware._extract_bearer_token(request)
        assert token == "test-token-123"

    def test_extract_bearer_token_case_insensitive(self, mock_settings):
        """Test that Bearer is case insensitive."""
        middleware = APIKeyAuthMiddleware(app=MagicMock(), settings=mock_settings)

        request = MagicMock()
        request.headers.get.return_value = "bearer test-token-123"

        token = middleware._extract_bearer_token(request)
        assert token == "test-token-123"

    def test_extract_bearer_token_missing_header(self, mock_settings):
        """Test extracting token when header is missing."""
        middleware = APIKeyAuthMiddleware(app=MagicMock(), settings=mock_settings)

        request = MagicMock()
        request.headers.get.return_value = None

        token = middleware._extract_bearer_token(request)
        assert token is None

    def test_extract_bearer_token_invalid_format(self, mock_settings):
        """Test extracting token with invalid format."""
        middleware = APIKeyAuthMiddleware(app=MagicMock(), settings=mock_settings)

        request = MagicMock()
        request.headers.get.return_value = "InvalidFormat test-token"

        token = middleware._extract_bearer_token(request)
        assert token is None


class TestRequestState:
    """Tests for request state population."""

    def test_authenticated_request_populates_state(
        self, api_key_manager, mock_settings
    ):
        """Test that successful auth populates request state."""
        from fastapi import Request

        # Create an API key
        api_key_request = APIKeyCreate(
            user_id="test-user", description="Test key", expires_days=30
        )
        key, token = api_key_manager.create_key(api_key_request)

        # Create a fresh app with custom route
        app = FastAPI()
        app.add_middleware(APIKeyAuthMiddleware, settings=mock_settings)

        @app.get("/api/check-state")
        async def check_state(request: Request):
            return {
                "user_id": getattr(request.state, "user_id", None),
                "has_api_key": hasattr(request.state, "api_key"),
            }

        # Make request with the token
        client = TestClient(app)
        response = client.get(
            "/api/check-state", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["user_id"] == "test-user"
        assert data["has_api_key"] is True
