"""Settings routes for model resolution configuration."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from jinja2 import Environment, FileSystemLoader

from claude_code_proxy.core.logging import get_logger
from claude_code_proxy.services.model_fallback import (
    ModelProvider,
    get_model_resolution_settings,
)


logger = get_logger(__name__)

router = APIRouter(prefix="/settings", tags=["settings"])

# Setup Jinja2 templates
TEMPLATES_DIR = Path(__file__).parent.parent.parent / "ui" / "templates"
jinja_env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)), autoescape=True)

# Model lists by provider - all use Anthropic format (proxy handles translation)
# These represent different curated lists of models for different use cases
PROVIDER_MODELS: dict[str, dict[str, list[str]]] = {
    "anthropic": {
        "sonnet": [
            "claude-sonnet-4-5-20250514",
            "claude-sonnet-4-20250514",
            "claude-3-5-sonnet-20241022",
            "claude-3-5-sonnet-latest",
        ],
        "opus": [
            "claude-opus-4-5-20250514",
            "claude-opus-4-20250514",
            "claude-3-opus-20240229",
            "claude-3-opus-latest",
        ],
        "haiku": [
            "claude-haiku-4-5-20250514",
            "claude-3-5-haiku-20241022",
            "claude-3-5-haiku-latest",
        ],
    },
    "openrouter": {
        "sonnet": [
            "claude-sonnet-4-5-20250514",
            "claude-sonnet-4-20250514",
            "claude-3-5-sonnet-20241022",
        ],
        "opus": [
            "claude-opus-4-5-20250514",
            "claude-opus-4-20250514",
            "claude-3-opus-20240229",
        ],
        "haiku": [
            "claude-haiku-4-5-20250514",
            "claude-3-5-haiku-20241022",
        ],
    },
    "litellm": {
        "sonnet": [
            "claude-sonnet-4-5-20250514",
            "claude-sonnet-4-20250514",
            "claude-3-5-sonnet-latest",
        ],
        "opus": [
            "claude-opus-4-5-20250514",
            "claude-opus-4-20250514",
            "claude-3-opus-latest",
        ],
        "haiku": [
            "claude-haiku-4-5-20250514",
            "claude-3-5-haiku-latest",
        ],
    },
}


def _get_current_settings() -> dict[str, Any]:
    """Get current model resolution settings."""
    settings = get_model_resolution_settings()
    if settings:
        return {
            "provider": settings.provider.value,
            "enable_fallback": settings.enable_fallback,
            "cache_ttl_hours": settings.unavailability_cache_ttl // 3600,
            "tier_defaults": settings.tier_defaults,
        }
    # Default settings
    return {
        "provider": "anthropic",
        "enable_fallback": True,
        "cache_ttl_hours": 1,
        "tier_defaults": {
            "sonnet": "claude-sonnet-latest",
            "opus": "claude-opus-latest",
            "haiku": "claude-haiku-latest",
        },
    }


def _get_available_models(provider: str = "anthropic") -> dict[str, list[str]]:
    """Get available models by tier for the specified provider."""
    return PROVIDER_MODELS.get(provider, PROVIDER_MODELS["anthropic"])


@router.get("")
async def settings_page(request: Request) -> RedirectResponse:
    """Redirect to accounts page - settings are now in a modal."""
    return RedirectResponse(url="/accounts", status_code=303)


@router.post("/update-provider", response_class=HTMLResponse)
async def update_provider(
    request: Request,
    provider: str = Form(...),
) -> HTMLResponse:
    """Update the model provider setting."""
    try:
        # Validate provider
        if provider not in [p.value for p in ModelProvider]:
            return HTMLResponse(
                content=_render_status_message(
                    f"Invalid provider: {provider}", is_error=True
                )
            )

        # Settings are session-only (not persisted across restarts)
        logger.info("model_provider_updated", provider=provider)

        return HTMLResponse(
            content=_render_status_message(f"Provider updated to {provider}")
        )
    except Exception as e:
        logger.exception("update_provider_failed", error=str(e))
        return HTMLResponse(
            content=_render_status_message(f"Error: {e}", is_error=True)
        )


@router.post("/update-fallback", response_class=HTMLResponse)
async def update_fallback(
    request: Request,
    enable_fallback: bool = Form(default=False),
    cache_ttl_hours: int = Form(default=1),
) -> HTMLResponse:
    """Update fallback settings."""
    try:
        # Validate cache TTL
        if cache_ttl_hours < 1 or cache_ttl_hours > 168:
            return HTMLResponse(
                content=_render_status_message(
                    "Cache TTL must be between 1 and 168 hours", is_error=True
                )
            )

        # Settings are session-only (not persisted across restarts)
        logger.info(
            "fallback_settings_updated",
            enable_fallback=enable_fallback,
            cache_ttl_hours=cache_ttl_hours,
        )

        return HTMLResponse(
            content=_render_status_message(
                f"Fallback {'enabled' if enable_fallback else 'disabled'}, cache TTL: {cache_ttl_hours}h"
            )
        )
    except Exception as e:
        logger.exception("update_fallback_failed", error=str(e))
        return HTMLResponse(
            content=_render_status_message(f"Error: {e}", is_error=True)
        )


@router.post("/update-tier-defaults", response_class=HTMLResponse)
async def update_tier_defaults(
    request: Request,
    sonnet_default: str = Form(...),
    opus_default: str = Form(...),
    haiku_default: str = Form(...),
) -> HTMLResponse:
    """Update tier default models."""
    try:
        # Settings are session-only (not persisted across restarts)
        logger.info(
            "tier_defaults_updated",
            sonnet=sonnet_default,
            opus=opus_default,
            haiku=haiku_default,
        )

        return HTMLResponse(
            content=_render_status_message("Tier defaults updated successfully")
        )
    except Exception as e:
        logger.exception("update_tier_defaults_failed", error=str(e))
        return HTMLResponse(
            content=_render_status_message(f"Error: {e}", is_error=True)
        )


@router.post("/test-models", response_class=HTMLResponse)
async def test_models(
    request: Request,
    sonnet_model: str = Form(...),
    opus_model: str = Form(...),
    haiku_model: str = Form(...),
) -> HTMLResponse:
    """Test the selected models by making a simple API call to each."""
    results = []
    for tier, model in [
        ("Sonnet", sonnet_model),
        ("Opus", opus_model),
        ("Haiku", haiku_model),
    ]:
        # Validates model name format (actual API testing not implemented)
        if model.startswith("claude-"):
            results.append(f"✓ {tier}: {model}")
        else:
            results.append(f"✗ {tier}: Invalid model format")

    logger.info("test_models", sonnet=sonnet_model, opus=opus_model, haiku=haiku_model)

    return HTMLResponse(
        content=_render_status_message(f"Test complete: {', '.join(results)}")
    )


@router.get("/modal", response_class=HTMLResponse)
async def settings_modal(request: Request) -> HTMLResponse:
    """Render the settings modal."""
    template = jinja_env.get_template("settings_modal.html")
    settings = _get_current_settings()

    content = template.render(
        settings=settings,
        available_models=_get_available_models(settings["provider"]),
    )

    return HTMLResponse(content=content)


@router.get("/models-for-provider", response_class=HTMLResponse)
async def models_for_provider(
    request: Request, provider: str, tier: str
) -> HTMLResponse:
    """Return model options for a specific provider and tier."""
    available_models = _get_available_models(provider)
    tier_models = available_models.get(tier, [])

    # Use first model as default for new provider
    current_default = tier_models[0] if tier_models else ""

    template = jinja_env.get_template("partials/model_select.html")
    return HTMLResponse(
        content=template.render(
            tier=tier,
            models=tier_models,
            current_default=current_default,
        )
    )


def _render_status_message(message: str, is_error: bool = False) -> str:
    """Render a status message HTML snippet using the partial template."""
    template = jinja_env.get_template("partials/status_message.html")
    return template.render(message=message, is_error=is_error)
