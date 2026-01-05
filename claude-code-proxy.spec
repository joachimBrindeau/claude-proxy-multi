# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller specification file for claude-code-proxy standalone binaries."""

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# Determine platform-specific binary name
platform = sys.platform
if platform == "darwin":
    binary_name = "claude-code-proxy-darwin-universal2"
elif platform == "linux":
    binary_name = "claude-code-proxy-linux-amd64"
elif platform == "win32":
    binary_name = "claude-code-proxy-windows-amd64.exe"
else:
    binary_name = "claude-code-proxy"

# Entry point
entry_point = "src/claude_code_proxy/cli/main.py"

# Collect all submodules for key dependencies
hiddenimports = [
    # Core dependencies
    "claude_code_proxy",
    "claude_code_proxy.cli",
    "claude_code_proxy.cli.main",
    "claude_code_proxy.cli.commands",
    "claude_code_proxy.api",
    "claude_code_proxy.ui",
    "claude_code_proxy.auth",
    "claude_code_proxy.config",
    "claude_code_proxy.rotation",
    "claude_code_proxy.claude_sdk",
    "claude_code_proxy.docker",
    "claude_code_proxy.models",
    "claude_code_proxy.scheduler",
    "claude_code_proxy.services",
    "claude_code_proxy.utils",
    "claude_code_proxy.core",
    "claude_code_proxy.adapters",
    # FastAPI and dependencies
    "uvicorn",
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    "fastapi",
    "starlette",
    "starlette.middleware",
    "starlette.middleware.cors",
    "pydantic",
    "pydantic_core",
    # HTTP clients
    "httpx",
    "httpx_sse",
    # Serialization
    "orjson",
    # Logging
    "structlog",
    "rich",
    # Storage
    "diskcache",
    "keyring",
    "keyring.backends",
    # Templating
    "jinja2",
    # Scheduling
    "apscheduler",
    "apscheduler.schedulers.asyncio",
    # Utilities
    "shortuuid",
    "tenacity",
    "pybreaker",
    "cachetools",
    # CLI
    "typer",
    # Textual (if used)
    "textual",
]

# Collect data files
datas = []

# Add UI templates
datas += [
    ("src/claude_code_proxy/ui/templates", "claude_code_proxy/ui/templates"),
]

# Add data files (JSON, etc.)
datas += [
    ("src/claude_code_proxy/data", "claude_code_proxy/data"),
]

# Add py.typed marker
py_typed = Path("src/claude_code_proxy/py.typed")
if py_typed.exists():
    datas += [("src/claude_code_proxy/py.typed", "claude_code_proxy")]

# Collect additional data files from dependencies
datas += collect_data_files("fastapi")
datas += collect_data_files("starlette")
datas += collect_data_files("pydantic")

a = Analysis(
    [entry_point],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude test modules
        "pytest",
        "pytest_asyncio",
        "pytest_cov",
        "pytest_httpx",
        # Exclude development tools
        "mypy",
        "ruff",
        "black",
        "pyright",
        # Exclude documentation tools
        "sphinx",
        "mkdocs",
        # Exclude unused backends
        "tkinter",
        "matplotlib",
        "numpy",
        "pandas",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name=binary_name,
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,  # Strip debug symbols for smaller size
    upx=True,  # Compress with UPX if available
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # Console application
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
