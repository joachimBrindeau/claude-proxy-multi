# tests/unit/auth/test_jwt_handler.py
"""Tests for JWT token handler."""

import pytest

from claude_code_proxy.auth.api_keys.jwt_handler import JWTHandler


class TestJWTHandler:
    """Tests for JWT token generation and validation."""

    def test_generate_token(self) -> None:
        """Test generating a JWT token."""
        handler = JWTHandler(secret_key="test-secret-key-32-chars-long!!")
        token = handler.generate_token(
            user_id="john",
            key_id="key-123",
            expires_days=90,
        )
        assert isinstance(token, str)
        assert len(token) > 50  # JWT tokens are long

    def test_validate_token(self) -> None:
        """Test validating a JWT token."""
        handler = JWTHandler(secret_key="test-secret-key-32-chars-long!!")
        token = handler.generate_token(
            user_id="john", key_id="key-123", expires_days=90
        )

        payload = handler.validate_token(token)
        assert payload["sub"] == "john"
        assert payload["kid"] == "key-123"

    def test_expired_token_raises(self) -> None:
        """Test that expired tokens raise an error."""
        handler = JWTHandler(secret_key="test-secret-key-32-chars-long!!")
        token = handler.generate_token(
            user_id="john", key_id="key-123", expires_days=-1
        )

        with pytest.raises(ValueError, match="Token has expired"):
            handler.validate_token(token)

    def test_invalid_signature_raises(self) -> None:
        """Test that tokens with wrong signature raise error."""
        handler1 = JWTHandler(secret_key="secret-key-1-32-chars-long!!!")
        handler2 = JWTHandler(secret_key="secret-key-2-32-chars-long!!!")

        token = handler1.generate_token(
            user_id="john", key_id="key-123", expires_days=90
        )

        with pytest.raises(ValueError, match="Invalid token"):
            handler2.validate_token(token)
