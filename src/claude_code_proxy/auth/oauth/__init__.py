"""OAuth authentication module for Anthropic OAuth login."""

from typing import TYPE_CHECKING

from claude_code_proxy.auth.oauth.models import (
    OAuthCallbackRequest,
    OAuthState,
    OAuthTokenRequest,
    OAuthTokenResponse,
)


# Lazy import to avoid circular dependency with routes
if TYPE_CHECKING:
    from claude_code_proxy.auth.oauth.routes import (
        get_oauth_flow_result,
        register_oauth_flow,
        router,
    )


def __getattr__(name: str) -> object:
    """Lazy import for routes to avoid circular dependencies."""
    if name in ("router", "register_oauth_flow", "get_oauth_flow_result"):
        from claude_code_proxy.auth.oauth.routes import (
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
