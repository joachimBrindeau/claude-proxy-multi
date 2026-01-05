"""Claude Code Proxy - Multi-account proxy with automatic rotation."""

# CRITICAL: Apply typing patch FIRST, before any other imports
# This fixes Pydantic incompatibility with typing.TypedDict on Python < 3.12
# Required for claude_code_sdk which uses typing.TypedDict
import typing

import typing_extensions


typing.TypedDict = typing_extensions.TypedDict

from ._version import __version__


__all__ = ["__version__"]
