"""OAuth client implementation for Anthropic OAuth flow."""

import asyncio
import base64
import hashlib
import os
import secrets
import time
import urllib.parse
import webbrowser
from dataclasses import dataclass
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
from typing import TYPE_CHECKING, Any
from urllib.parse import parse_qs, urlparse

import httpx
from structlog import get_logger

from claude_code_proxy.auth.models import ClaudeCredentials, OAuthToken, UserProfile
from claude_code_proxy.auth.oauth.models import OAuthTokenRequest, OAuthTokenResponse
from claude_code_proxy.exceptions import OAuthCallbackError, OAuthLoginError


if TYPE_CHECKING:
    from claude_code_proxy.config.auth import OAuthSettings


logger = get_logger(__name__)


@dataclass
class OAuthCallbackResult:
    """Container for OAuth callback results."""

    authorization_code: str | None = None
    error: str | None = None


def _create_oauth_callback_handler(
    expected_state: str, result: OAuthCallbackResult
) -> type[BaseHTTPRequestHandler]:
    """Create an OAuth callback HTTP request handler.

    Args:
        expected_state: Expected state parameter for CSRF protection
        result: Mutable container to store callback results

    Returns:
        A BaseHTTPRequestHandler subclass for processing OAuth callbacks
    """

    class OAuthCallbackHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            if self.path == "/favicon.ico":
                self.send_response(404)
                self.end_headers()
                return

            parsed_url = urlparse(self.path)
            query_params = parse_qs(parsed_url.query)
            received_state = query_params.get("state", [None])[0]

            if received_state != expected_state:
                result.error = "Invalid state parameter"
                self._send_error("Invalid state parameter")
            elif "code" in query_params:
                result.authorization_code = query_params["code"][0]
                self._send_success()
            elif "error" in query_params:
                result.error = query_params.get("error_description", ["Unknown error"])[
                    0
                ]
                self._send_error(result.error)
            else:
                result.error = "No authorization code received"
                self._send_error("No authorization code received")

        def _send_success(self) -> None:
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Login successful! You can close this window.")

        def _send_error(self, message: str | None) -> None:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(f"Error: {message}".encode())

        def log_message(self, format: str, *args: Any) -> None:
            pass  # Suppress HTTP server logs

    return OAuthCallbackHandler


def _truncate_error_text(response_text: str) -> str:
    """Truncate response text for compact error logging.

    Args:
        response_text: Full response text

    Returns:
        Truncated text suitable for logging
    """
    if len(response_text) > 200:
        return f"{response_text[:100]}...{response_text[-50:]}"
    elif len(response_text) > 100:
        return f"{response_text[:100]}..."
    return response_text


def _log_http_error_compact(operation: str, response: httpx.Response) -> None:
    """Log HTTP error response in compact format.

    Args:
        operation: Description of the operation that failed
        response: HTTP response object
    """
    verbose_api = os.environ.get("CCPROXY_VERBOSE_API", "false").lower() == "true"

    if verbose_api:
        logger.error(
            "http_operation_failed",
            operation=operation,
            status_code=response.status_code,
            response_text=response.text,
        )
    else:
        logger.error(
            "http_operation_failed_compact",
            operation=operation,
            status_code=response.status_code,
            response_preview=_truncate_error_text(response.text),
            verbose_hint="use CCPROXY_VERBOSE_API=true for full response",
        )


class OAuthClient:
    """OAuth client for handling Anthropic OAuth flows."""

    def __init__(self, config: "OAuthSettings | None" = None):
        """Initialize OAuth client.

        Args:
            config: OAuth configuration, uses default if not provided
        """
        # Lazy import to avoid circular dependency
        if config is None:
            from claude_code_proxy.config.auth import OAuthSettings

            config = OAuthSettings()
        self.config = config

    def generate_pkce_pair(self) -> tuple[str, str]:
        """Generate PKCE code verifier and challenge pair.

        Returns:
            Tuple of (code_verifier, code_challenge)
        """
        # Generate code verifier (43-128 characters, URL-safe)
        code_verifier = secrets.token_urlsafe(96)  # 128 base64url chars

        # For now, use plain method (Anthropic supports this)
        # In production, should use SHA256 method
        code_challenge = code_verifier

        return code_verifier, code_challenge

    def build_authorization_url(self, state: str, code_challenge: str) -> str:
        """Build authorization URL for OAuth flow.

        Args:
            state: State parameter for CSRF protection
            code_challenge: PKCE code challenge

        Returns:
            Authorization URL
        """
        params = {
            "code": "true",  # Required: tells Claude to show code on callback page
            "response_type": "code",
            "client_id": self.config.client_id,
            "redirect_uri": self.config.redirect_uri,
            "scope": " ".join(self.config.scopes),
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "plain",  # Using plain for simplicity
        }

        query_string = urllib.parse.urlencode(params)
        return f"{self.config.authorize_url}?{query_string}"

    async def exchange_code_for_tokens(
        self,
        authorization_code: str,
        code_verifier: str,
    ) -> OAuthTokenResponse:
        """Exchange authorization code for access tokens.

        Args:
            authorization_code: Authorization code from callback
            code_verifier: PKCE code verifier

        Returns:
            Token response

        Raises:
            httpx.HTTPError: If token exchange fails
        """
        token_request = OAuthTokenRequest(
            code=authorization_code,
            redirect_uri=self.config.redirect_uri,
            client_id=self.config.client_id,
            code_verifier=code_verifier,
        )

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "anthropic-beta": self.config.beta_version,
            "User-Agent": self.config.user_agent,
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.config.token_url,
                headers=headers,
                data=token_request.model_dump(),  # form-encoded
                timeout=self.config.request_timeout,
            )

            if response.status_code != 200:
                _log_http_error_compact("Token exchange", response)
                response.raise_for_status()

            data = response.json()
            return OAuthTokenResponse.model_validate(data)

    async def refresh_access_token(self, refresh_token: str) -> OAuthTokenResponse:
        """Refresh access token using refresh token.

        Args:
            refresh_token: Refresh token

        Returns:
            New token response

        Raises:
            httpx.HTTPError: If token refresh fails
        """
        refresh_request = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": self.config.client_id,
        }

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "anthropic-beta": self.config.beta_version,
            "User-Agent": self.config.user_agent,
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.config.token_url,
                headers=headers,
                data=refresh_request,  # form-encoded
                timeout=self.config.request_timeout,
            )

            if response.status_code != 200:
                _log_http_error_compact("Token refresh", response)
                response.raise_for_status()

            data = response.json()
            return OAuthTokenResponse.model_validate(data)

    async def refresh_token(self, refresh_token: str) -> "OAuthToken":
        """Refresh token using refresh token - compatibility method for tests.

        Args:
            refresh_token: Refresh token

        Returns:
            New OAuth token

        Raises:
            OAuthTokenRefreshError: If token refresh fails
        """
        from datetime import UTC, datetime

        from claude_code_proxy.auth.models import OAuthToken
        from claude_code_proxy.exceptions import OAuthTokenRefreshError

        try:
            token_response = await self.refresh_access_token(refresh_token)

            expires_in = (
                token_response.expires_in if token_response.expires_in else 3600
            )

            # Convert to OAuthToken format expected by tests
            expires_at_ms = int((datetime.now(UTC).timestamp() + expires_in) * 1000)

            return OAuthToken(
                accessToken=token_response.access_token,
                refreshToken=token_response.refresh_token or refresh_token,
                expiresAt=expires_at_ms,
                scopes=token_response.scope.split() if token_response.scope else [],
                subscriptionType="pro",  # Default value
            )
        except httpx.HTTPError as e:
            # HTTP transport errors (connection, timeout, protocol issues)
            raise OAuthTokenRefreshError(f"Token refresh failed: {e}") from e

    async def fetch_user_profile(self, access_token: str) -> UserProfile | None:
        """Fetch user profile information using access token.

        Args:
            access_token: Valid OAuth access token

        Returns:
            User profile information

        Raises:
            httpx.HTTPError: If profile fetch fails
        """
        from claude_code_proxy.auth.models import UserProfile

        headers = {
            "Authorization": f"Bearer {access_token}",
            "anthropic-beta": self.config.beta_version,
            "User-Agent": self.config.user_agent,
            "Content-Type": "application/json",
        }

        # Use the profile url
        async with httpx.AsyncClient() as client:
            response = await client.get(
                self.config.profile_url,
                headers=headers,
                timeout=self.config.request_timeout,
            )

            if response.status_code == 404:
                # Userinfo endpoint not available - this is expected for some OAuth providers
                logger.debug(
                    "userinfo_endpoint_unavailable", endpoint=self.config.profile_url
                )
                return None
            elif response.status_code != 200:
                _log_http_error_compact("Profile fetch", response)
                response.raise_for_status()

            data = response.json()
            logger.debug("user_profile_fetched", endpoint=self.config.profile_url)
            return UserProfile.model_validate(data)

    def _generate_pkce_sha256(self) -> tuple[str, str]:
        """Generate PKCE parameters using SHA256.

        Returns:
            Tuple of (code_verifier, code_challenge)
        """
        code_verifier = secrets.token_urlsafe(32)
        code_challenge = (
            base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest())
            .decode()
            .rstrip("=")
        )
        return code_verifier, code_challenge

    def _build_auth_url(self, state: str, code_challenge: str) -> str:
        """Build OAuth authorization URL with SHA256 challenge.

        Args:
            state: CSRF state parameter
            code_challenge: PKCE code challenge

        Returns:
            Complete authorization URL
        """
        auth_params = {
            "code": "true",
            "response_type": "code",
            "client_id": self.config.client_id,
            "redirect_uri": self.config.redirect_uri,
            "scope": " ".join(self.config.scopes),
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
        return f"{self.config.authorize_url}?{urllib.parse.urlencode(auth_params)}"

    async def _wait_for_callback(
        self, result: OAuthCallbackResult, timeout: float
    ) -> None:
        """Wait for OAuth callback with timeout.

        Args:
            result: Mutable result container
            timeout: Maximum wait time in seconds

        Raises:
            OAuthCallbackError: If callback fails or times out
        """
        start_time = time.time()
        while result.authorization_code is None and result.error is None:
            if time.time() - start_time > timeout:
                result.error = "Login timeout"
                break
            await asyncio.sleep(0.1)

        if result.error:
            raise OAuthCallbackError(f"OAuth callback failed: {result.error}")

    async def _exchange_tokens(
        self, authorization_code: str, code_verifier: str
    ) -> httpx.Response:
        """Exchange authorization code for tokens.

        Args:
            authorization_code: Code from OAuth callback
            code_verifier: PKCE code verifier

        Returns:
            HTTP response from token endpoint
        """
        token_data = {
            "grant_type": "authorization_code",
            "code": authorization_code,
            "redirect_uri": self.config.redirect_uri,
            "client_id": self.config.client_id,
            "code_verifier": code_verifier,
        }
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "anthropic-beta": self.config.beta_version,
            "User-Agent": self.config.user_agent,
        }
        async with httpx.AsyncClient() as client:
            return await client.post(
                self.config.token_url, headers=headers, data=token_data, timeout=30.0
            )

    def _parse_token_response(self, response_data: dict[str, Any]) -> ClaudeCredentials:
        """Parse token response into ClaudeCredentials.

        Args:
            response_data: JSON response from token endpoint

        Returns:
            ClaudeCredentials object
        """
        expires_in = response_data.get("expires_in")
        expires_at = None
        if expires_in:
            expires_at = int((datetime.now(UTC).timestamp() + expires_in) * 1000)

        scope = response_data.get("scope", "")
        scopes = scope.split() if scope else self.config.scopes

        oauth_data = {
            "accessToken": response_data.get("access_token"),
            "refreshToken": response_data.get("refresh_token"),
            "expiresAt": expires_at,
            "scopes": scopes,
            "subscriptionType": response_data.get("subscription_type", "unknown"),
        }
        return ClaudeCredentials(claudeAiOauth=OAuthToken(**oauth_data))

    async def login(self) -> ClaudeCredentials:
        """Perform OAuth login flow.

        Returns:
            ClaudeCredentials with OAuth token

        Raises:
            OAuthLoginError: If login fails
            OAuthCallbackError: If callback processing fails
        """
        state = secrets.token_urlsafe(32)
        code_verifier, code_challenge = self._generate_pkce_sha256()
        callback_result = OAuthCallbackResult()

        handler_class = _create_oauth_callback_handler(state, callback_result)
        server = HTTPServer(("localhost", self.config.callback_port), handler_class)
        server_thread = Thread(target=server.serve_forever, daemon=True)
        server_thread.start()

        try:
            auth_url = self._build_auth_url(state, code_challenge)
            logger.info("oauth_browser_opening", auth_url=auth_url)
            logger.info(
                "oauth_manual_url",
                message="If browser doesn't open, visit this URL",
                auth_url=auth_url,
            )
            webbrowser.open(auth_url)

            await self._wait_for_callback(callback_result, self.config.callback_timeout)

            if not callback_result.authorization_code:
                raise OAuthLoginError("No authorization code received")

            response = await self._exchange_tokens(
                callback_result.authorization_code, code_verifier
            )

            if response.status_code == 200:
                credentials = self._parse_token_response(response.json())
                logger.info("oauth_login_completed", client_id=self.config.client_id)
                return credentials

            verbose = os.environ.get("CCPROXY_VERBOSE_API", "false").lower() == "true"
            error_detail = (
                response.text if verbose else _truncate_error_text(response.text)
            )
            raise OAuthLoginError(
                f"Token exchange failed: {response.status_code} - {error_detail}"
            )

        except (httpx.HTTPError, httpx.TimeoutException) as e:
            raise OAuthLoginError(f"OAuth login failed: {e}") from e

        finally:
            server.shutdown()
            server_thread.join(timeout=1)
