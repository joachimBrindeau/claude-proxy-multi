"""Claude SDK exceptions.

DEPRECATED: This module is deprecated. Import from ccproxy.exceptions instead.
Re-exports are provided for backwards compatibility.
"""

from ccproxy.exceptions import ClaudeSDKError, StreamTimeoutError


__all__ = [
    "ClaudeSDKError",
    "StreamTimeoutError",
]
