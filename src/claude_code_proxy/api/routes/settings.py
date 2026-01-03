"""Settings routes for model resolution configuration."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse
from jinja2 import Environment, FileSystemLoader

from claude_code_proxy.core.logging import get_logger
from claude_code_proxy.services.model_fallback import (
    ModelProvider,
    ModelResolutionSettings,
    get_fallback_resolver,
    get_model_resolution_settings,
)
from claude_code_proxy.services.model_resolver import get_model_resolver

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)

router = APIRouter(prefix="/settings", tags=["settings"])

# Setup Jinja2 templates
TEMPLATES_DIR = Path(__file__).parent.parent.parent / "ui" / "templates"
jinja_env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)), autoescape=True)


def _get_current_settings() -> dict:
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


def _get_available_models() -> dict[str, list[str]]:
    """Get available models by tier from the resolver."""
    resolver = get_model_resolver()
    if resolver:
        tier_models = resolver.get_models_by_tier()
        return {
            "sonnet": tier_models.get("sonnet", ["claude-sonnet-4-5"]),
            "opus": tier_models.get("opus", ["claude-opus-4-5"]),
            "haiku": tier_models.get("haiku", ["claude-haiku-4-5"]),
        }
    # Fallback defaults
    return {
        "sonnet": ["claude-sonnet-4-5", "claude-sonnet-4", "claude-3-5-sonnet-20241022"],
        "opus": ["claude-opus-4-5", "claude-opus-4", "claude-3-opus-20240229"],
        "haiku": ["claude-haiku-4-5", "claude-3-5-haiku-20241022"],
    }


def _get_current_mappings() -> dict[str, str]:
    """Get current tier-to-model mappings."""
    resolver = get_model_resolver()
    if resolver:
        return resolver.get_cached_mappings()
    return {
        "sonnet": "claude-sonnet-4-5",
        "opus": "claude-opus-4-5",
        "haiku": "claude-haiku-4-5",
    }


def _get_last_refresh() -> str | None:
    """Get last refresh timestamp as formatted string."""
    resolver = get_model_resolver()
    if resolver and resolver.last_refresh:
        return resolver.last_refresh.strftime("%Y-%m-%d %H:%M:%S UTC")
    return None


@router.get("", response_class=HTMLResponse)
async def settings_page(request: Request, status_message: str | None = None) -> HTMLResponse:
    """Render the settings page."""
    template = jinja_env.get_template("settings.html")

    content = template.render(
        settings=_get_current_settings(),
        available_models=_get_available_models(),
        current_mappings=_get_current_mappings(),
        last_refresh=_get_last_refresh(),
        status_message=status_message,
    )

    return HTMLResponse(content=content)


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
                content=_render_status_message(f"Invalid provider: {provider}", is_error=True)
            )

        # TODO: Persist settings to file/database
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

        # TODO: Persist settings to file/database
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
        # TODO: Persist settings to file/database
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


@router.get("/refresh-status", response_class=HTMLResponse)
async def refresh_status(request: Request) -> HTMLResponse:
    """Refresh and return current resolution status."""
    resolver = get_model_resolver()
    if resolver:
        try:
            await resolver.refresh()
        except Exception as e:
            logger.warning("status_refresh_failed", error=str(e))

    mappings = _get_current_mappings()
    last_refresh = _get_last_refresh()

    # Build HTML for status display
    html_parts = []
    for tier, model in mappings.items():
        html_parts.append(f'''
            <div class="flex items-center justify-between p-3 rounded-lg bg-slate-50">
                <code class="text-sm text-slate-600">claude-{tier}-latest</code>
                <code class="text-sm font-medium text-slate-900">{model}</code>
            </div>
        ''')

    if last_refresh:
        html_parts.append(f'<p class="text-xs text-slate-400 mt-3">Last refreshed: {last_refresh}</p>')

    return HTMLResponse(content="\n".join(html_parts))


def _render_status_message(message: str, is_error: bool = False) -> str:
    """Render a status message HTML snippet."""
    if is_error:
        return f'''
            <div class="mb-6 px-4 py-3 rounded-xl text-sm fade-in flex items-start gap-3 bg-red-50 text-red-800 border border-red-100">
                <svg class="w-5 h-5 flex-shrink-0 mt-0.5 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <span>{message}</span>
            </div>
        '''
    return f'''
        <div class="mb-6 px-4 py-3 rounded-xl text-sm fade-in flex items-start gap-3 bg-emerald-50 text-emerald-800 border border-emerald-100">
            <svg class="w-5 h-5 flex-shrink-0 mt-0.5 text-emerald-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <span>{message}</span>
        </div>
    '''
