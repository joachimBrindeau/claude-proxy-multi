"""Root route for CCProxy - landing page and setup redirect."""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from structlog import get_logger

from claude_code_proxy import __version__
from claude_code_proxy.rotation.pool import RotationPool


logger = get_logger(__name__)
router = APIRouter()


def get_pool(request: Request) -> RotationPool | None:
    """Get rotation pool from app state."""
    return getattr(request.app.state, "rotation_pool", None)


@router.get("/", response_model=None)
async def root(request: Request) -> HTMLResponse | RedirectResponse:
    """Root landing page.

    Redirects to /accounts/ if no accounts configured (first-run setup).
    Otherwise shows a welcome page with links.
    """
    pool = get_pool(request)

    # Check if setup is needed (no accounts or pool not initialized)
    if pool is None or pool.account_count == 0:
        logger.info("setup_required_redirect", reason="no_accounts")
        return RedirectResponse(url="/accounts/", status_code=302)

    # Show welcome page with status
    status = pool.get_status()
    total = status.get("totalAccounts", 0)
    available = status.get("availableAccounts", 0)

    return HTMLResponse(
        content=f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CCProxy - Claude Code Proxy</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-900 text-slate-100 min-h-screen flex items-center justify-center">
    <div class="max-w-lg mx-auto p-8 text-center">
        <h1 class="text-4xl font-bold mb-2">CCProxy</h1>
        <p class="text-slate-400 mb-8">Claude Code Multi-Account Proxy</p>

        <div class="bg-slate-800 rounded-lg p-6 mb-8">
            <div class="grid grid-cols-2 gap-4 text-left">
                <div>
                    <p class="text-slate-400 text-sm">Version</p>
                    <p class="font-mono">{__version__}</p>
                </div>
                <div>
                    <p class="text-slate-400 text-sm">Accounts</p>
                    <p class="font-mono">{available}/{total} ready</p>
                </div>
            </div>
        </div>

        <div class="space-y-4">
            <a href="/accounts/" class="block w-full bg-blue-600 hover:bg-blue-700 text-white font-medium py-3 px-6 rounded-lg transition">
                Manage Accounts
            </a>
            <a href="/health" class="block w-full bg-slate-700 hover:bg-slate-600 text-white font-medium py-3 px-6 rounded-lg transition">
                Health Status
            </a>
            <a href="/rotation/status" class="block w-full bg-slate-700 hover:bg-slate-600 text-white font-medium py-3 px-6 rounded-lg transition">
                Rotation Status
            </a>
            <a href="/docs" class="block w-full bg-slate-700 hover:bg-slate-600 text-white font-medium py-3 px-6 rounded-lg transition">
                API Documentation
            </a>
        </div>

        <p class="text-slate-500 text-sm mt-8">
            API endpoint: <code class="bg-slate-800 px-2 py-1 rounded">/api/v1/messages</code>
        </p>
    </div>
</body>
</html>""",
        status_code=200,
    )
