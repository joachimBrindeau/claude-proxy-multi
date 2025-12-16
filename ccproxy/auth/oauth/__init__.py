"""OAuth authentication module for Anthropic OAuth login."""

from typing import TYPE_CHECKING

from ccproxy.auth.oauth.models import (
    OAuthCallbackRequest,
    OAuthState,
    OAuthTokenRequest,
    OAuthTokenResponse,
)


# Lazy import to avoid circular dependency with routes
if TYPE_CHECKING:
    from ccproxy.auth.oauth.routes import (
        get_oauth_flow_result,
        register_oauth_flow,
        router,
    )


def __getattr__(name: str):
    """Lazy import for routes to avoid circular dependencies."""
    if name in ("router", "register_oauth_flow", "get_oauth_flow_result"):
        from ccproxy.auth.oauth.routes import (
            get_oauth_flow_result,
            register_oauth_flow,
            router,
        )
        return locals()[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    # Router
    "router",
    "register_oauth_flow",
    "get_oauth_flow_result",
    # Models
    "OAuthState",
    "OAuthCallbackRequest",
    "OAuthTokenRequest",
    "OAuthTokenResponse",
]
