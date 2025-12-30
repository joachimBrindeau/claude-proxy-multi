"""Multi-account rotation module for ccproxy.

This module provides automatic rotation between multiple Claude accounts
with rate limit failover and proactive token refresh.
"""

from ccproxy.rotation.accounts import (
    Account,
    AccountCredentials,
    AccountsFile,
    load_accounts,
    save_accounts,
)
from ccproxy.rotation.file_watcher import AccountsFileWatcher
from ccproxy.rotation.pool import AccountState, RotationPool
from ccproxy.rotation.refresh import TokenRefreshScheduler


__all__ = [
    "Account",
    "AccountCredentials",
    "AccountsFile",
    "AccountsFileWatcher",
    "AccountState",
    "RotationPool",
    "TokenRefreshScheduler",
    "load_accounts",
    "save_accounts",
]
