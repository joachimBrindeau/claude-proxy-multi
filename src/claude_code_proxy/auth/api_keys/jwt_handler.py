"""JWT token generation and validation for API keys."""

from datetime import UTC, datetime, timedelta

import jwt
from structlog import get_logger


logger = get_logger(__name__)


class JWTHandler:
    """Handles JWT token generation and validation for API keys."""

    ALGORITHM = "HS256"

    def __init__(self, secret_key: str) -> None:
        """Initialize JWT handler with secret key.

        Args:
            secret_key: Secret key for signing tokens (min 32 chars recommended)

        """
        if len(secret_key) < 32:
            logger.warning("jwt_secret_key_short", length=len(secret_key))
        self.secret_key = secret_key

    def generate_token(
        self,
        user_id: str,
        key_id: str,
        expires_days: int,
    ) -> str:
        """Generate a signed JWT token.

        Args:
            user_id: User identifier to embed in token
            key_id: Unique key identifier
            expires_days: Number of days until expiration

        Returns:
            Encoded JWT token string

        """
        now = datetime.now(UTC)
        payload = {
            "sub": user_id,  # Subject (user)
            "kid": key_id,  # Key ID
            "iat": now,  # Issued at
            "exp": now + timedelta(days=expires_days),  # Expiration
            "iss": "claude-code-proxy",  # Issuer
        }
        return jwt.encode(payload, self.secret_key, algorithm=self.ALGORITHM)

    def validate_token(self, token: str) -> dict[str, str]:
        """Validate and decode a JWT token.

        Args:
            token: JWT token string

        Returns:
            Decoded payload dictionary

        Raises:
            ValueError: If token is invalid or expired

        """
        try:
            payload: dict[str, str] = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.ALGORITHM],
                options={"require": ["sub", "kid", "exp"]},
            )
            return payload
        except jwt.ExpiredSignatureError as e:
            raise ValueError("Token has expired") from e
        except jwt.InvalidTokenError as e:
            raise ValueError(f"Invalid token: {e}") from e
