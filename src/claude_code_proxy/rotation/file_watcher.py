"""File watcher for hot-reload of accounts.json.

Monitors the accounts file for changes and triggers pool reload.
Uses watchdog for efficient file system event monitoring.
"""

import asyncio
from collections.abc import Callable, Coroutine
from pathlib import Path
from typing import Any, cast

from structlog import get_logger
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer


logger = get_logger(__name__)

# Type aliases for callbacks
SyncCallback = Callable[[], None]
AsyncCallback = Callable[[], Coroutine[Any, Any, None]]
OnChangeCallback = SyncCallback | AsyncCallback


class AccountsFileHandler(FileSystemEventHandler):
    """Handler for accounts.json file changes."""

    def __init__(
        self,
        accounts_path: Path,
        on_change: OnChangeCallback,
        debounce_seconds: float = 1.0,
    ):
        """Initialize file handler.

        Args:
            accounts_path: Path to accounts.json
            on_change: Callback to invoke on file change (sync or async)
            debounce_seconds: Debounce interval to avoid duplicate events
        """
        super().__init__()
        self._accounts_path = accounts_path
        self._on_change = on_change
        self._debounce_seconds = debounce_seconds
        self._last_event_time: float = 0
        self._loop: asyncio.AbstractEventLoop | None = None
        self._is_async_callback = asyncio.iscoroutinefunction(on_change)

    def set_event_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Set the event loop for async callbacks.

        Args:
            loop: Event loop to use for scheduling callbacks
        """
        self._loop = loop

    def on_modified(self, event: FileSystemEvent) -> None:
        """Handle file modification event.

        Args:
            event: File system event
        """
        if event.is_directory:
            return

        raw_path = event.src_path
        if isinstance(raw_path, bytes):
            try:
                src_path = raw_path.decode("utf-8")
            except UnicodeDecodeError:
                # Fall back to surrogateescape for non-UTF-8 paths
                src_path = raw_path.decode("utf-8", errors="surrogateescape")
                logger.warning(
                    "non_utf8_path_detected",
                    raw_path=repr(raw_path),
                )
        else:
            src_path = raw_path
        event_path = Path(src_path)
        if event_path.name != self._accounts_path.name:
            return

        # Debounce duplicate events
        import time

        current_time = time.time()
        if current_time - self._last_event_time < self._debounce_seconds:
            return

        self._last_event_time = current_time

        logger.info(
            "accounts_file_modified",
            path=str(event_path),
        )

        # Schedule callback in the event loop (thread-safe)
        if self._loop and self._is_async_callback:
            # For async callbacks, use run_coroutine_threadsafe
            async_cb = cast(AsyncCallback, self._on_change)
            coro = async_cb()
            asyncio.run_coroutine_threadsafe(coro, self._loop)
        elif self._loop:
            # For sync callbacks, schedule in event loop
            self._loop.call_soon_threadsafe(cast(SyncCallback, self._on_change))
        else:
            # No event loop - direct call (sync only)
            if not self._is_async_callback:
                cast(SyncCallback, self._on_change)()

    def on_created(self, event: FileSystemEvent) -> None:
        """Handle file creation event (new accounts file).

        Args:
            event: File system event
        """
        # Treat creation the same as modification
        self.on_modified(event)


class AccountsFileWatcher:
    """Watches accounts.json for changes and triggers hot-reload.

    Features:
    - Efficient file system monitoring via watchdog
    - Debouncing to handle duplicate events
    - Thread-safe integration with async event loop
    """

    def __init__(
        self,
        accounts_path: Path,
        on_reload: OnChangeCallback,
        debounce_seconds: float = 1.0,
    ):
        """Initialize file watcher.

        Args:
            accounts_path: Path to accounts.json
            on_reload: Callback to invoke when file changes
            debounce_seconds: Debounce interval
        """
        self._accounts_path = Path(accounts_path).expanduser()
        self._on_reload = on_reload
        self._debounce_seconds = debounce_seconds
        self._observer: Any = None  # Observer type from watchdog
        self._running = False

    @property
    def is_running(self) -> bool:
        """Check if watcher is running."""
        return self._running

    def start(self) -> None:
        """Start watching the accounts file."""
        if self._running:
            logger.warning("file_watcher_already_running")
            return

        # Get the directory to watch
        watch_dir = self._accounts_path.parent
        if not watch_dir.exists():
            logger.warning(
                "accounts_directory_not_found",
                directory=str(watch_dir),
                message="Creating directory for accounts.json",
            )
            watch_dir.mkdir(parents=True, exist_ok=True)

        # Create handler and observer
        handler = AccountsFileHandler(
            accounts_path=self._accounts_path,
            on_change=self._on_reload,
            debounce_seconds=self._debounce_seconds,
        )

        # Set event loop for async callbacks
        try:
            loop = asyncio.get_running_loop()
            handler.set_event_loop(loop)
        except RuntimeError:
            # No running loop - callbacks will be synchronous
            pass

        self._observer = Observer()
        self._observer.schedule(handler, str(watch_dir), recursive=False)
        self._observer.start()
        self._running = True

        logger.info(
            "file_watcher_started",
            watching=str(self._accounts_path),
            directory=str(watch_dir),
        )

    def stop(self) -> None:
        """Stop watching the accounts file."""
        if not self._running:
            return

        if self._observer:
            self._observer.stop()
            self._observer.join(timeout=5.0)
            self._observer = None

        self._running = False
        logger.info("file_watcher_stopped")


# Global watcher instance
_watcher: AccountsFileWatcher | None = None


def get_file_watcher() -> AccountsFileWatcher | None:
    """Get the global file watcher instance.

    Returns:
        AccountsFileWatcher instance or None if not initialized
    """
    return _watcher


def init_file_watcher(
    accounts_path: Path,
    on_reload: OnChangeCallback,
) -> AccountsFileWatcher:
    """Initialize the global file watcher.

    Args:
        accounts_path: Path to accounts.json
        on_reload: Callback to invoke when file changes

    Returns:
        Initialized AccountsFileWatcher
    """
    global _watcher
    _watcher = AccountsFileWatcher(accounts_path, on_reload)
    return _watcher
