"""Multi-account rotation module for claude-code-proxy.

This module provides automatic rotation between multiple Claude accounts
with rate limit failover and proactive token refresh.
"""

from claude_code_proxy.rotation.accounts import (
    Account,
    AccountCredentials,
    AccountsFile,
    load_accounts,
    save_accounts,
)
from claude_code_proxy.rotation.file_watcher import AccountsFileWatcher
from claude_code_proxy.rotation.pool import AccountState, RotationPool
from claude_code_proxy.rotation.refresh import TokenRefreshScheduler


__all__ = [
    "Account",
    "AccountCredentials",
    "AccountState",
    "AccountsFile",
    "AccountsFileWatcher",
    "RotationPool",
    "TokenRefreshScheduler",
    "load_accounts",
    "save_accounts",
]
