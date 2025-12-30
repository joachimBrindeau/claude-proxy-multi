"""Async utilities for the CCProxy API."""

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from contextlib import asynccontextmanager, contextmanager
from functools import wraps
from pathlib import Path
from typing import Any, TypeVar

from cachetools import TTLCache
from packaging.version import InvalidVersion, Version


T = TypeVar("T")


# Extract the typing fix from utils/helper.py
@contextmanager
def patched_typing() -> Iterator[None]:
    """Fix for typing.TypedDict not supported in older Python versions.

    This patches typing.TypedDict to use typing_extensions.TypedDict.
    """
    import typing

    import typing_extensions

    original = typing.TypedDict
    typing.TypedDict = typing_extensions.TypedDict
    try:
        yield
    finally:
        typing.TypedDict = original


def get_package_dir() -> Path:
    """Get the package directory path.

    Returns:
        Path to the package directory
    """
    try:
        import importlib.util

        # Get the path to the ccproxy package and resolve it
        spec = importlib.util.find_spec(get_root_package_name())
        if spec and spec.origin:
            package_dir = Path(spec.origin).parent.parent.resolve()
        else:
            package_dir = Path(__file__).parent.parent.parent.resolve()
    except (ModuleNotFoundError, ImportError, AttributeError):
        # ModuleNotFoundError: Package not found
        # ImportError: Import system error
        # AttributeError: spec.origin access failed
        package_dir = Path(__file__).parent.parent.parent.resolve()

    return package_dir


def get_root_package_name() -> str:
    """Get the root package name.

    Returns:
        The root package name
    """
    if __package__:
        return __package__.split(".")[0]
    return __name__.split(".")[0]


async def run_in_executor(func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    """Run a synchronous function in an executor.

    Args:
        func: The synchronous function to run
        *args: Positional arguments to pass to the function
        **kwargs: Keyword arguments to pass to the function

    Returns:
        The result of the function call
    """
    loop = asyncio.get_event_loop()

    # Create a partial function if we have kwargs
    if kwargs:
        from functools import partial

        func = partial(func, **kwargs)

    return await loop.run_in_executor(None, func, *args)


async def safe_await(awaitable: Awaitable[T], timeout: float | None = None) -> T | None:
    """Safely await an awaitable with optional timeout.

    Args:
        awaitable: The awaitable to wait for
        timeout: Optional timeout in seconds

    Returns:
        The result of the awaitable or None if timeout/error
    """
    try:
        if timeout is not None:
            return await asyncio.wait_for(awaitable, timeout=timeout)
        return await awaitable
    except TimeoutError:
        # Timeout from asyncio.wait_for
        return None
    except asyncio.CancelledError:
        # Task was cancelled
        return None


async def gather_with_concurrency(
    limit: int, *awaitables: Awaitable[T], return_exceptions: bool = False
) -> list[T | BaseException] | list[T]:
    """Gather awaitables with concurrency limit.

    Args:
        limit: Maximum number of concurrent operations
        *awaitables: Awaitables to execute
        return_exceptions: Whether to return exceptions as results

    Returns:
        List of results from the awaitables
    """
    semaphore = asyncio.Semaphore(limit)

    async def _limited_awaitable(awaitable: Awaitable[T]) -> T:
        async with semaphore:
            return await awaitable

    limited_awaitables = [_limited_awaitable(aw) for aw in awaitables]
    if return_exceptions:
        return await asyncio.gather(*limited_awaitables, return_exceptions=True)
    else:
        return await asyncio.gather(*limited_awaitables)


@asynccontextmanager
async def async_timer() -> AsyncIterator[Callable[[], float]]:
    """Context manager for timing async operations.

    Yields:
        Function that returns elapsed time in seconds
    """
    import time

    start_time = time.perf_counter()

    def get_elapsed() -> float:
        return time.perf_counter() - start_time

    yield get_elapsed


async def wait_for_condition(
    condition: Callable[[], bool | Awaitable[bool]],
    timeout: float = 30.0,
    interval: float = 0.1,
) -> bool:
    """Wait for a condition to become true.

    Args:
        condition: Function that returns True when condition is met
        timeout: Maximum time to wait in seconds
        interval: Check interval in seconds

    Returns:
        True if condition was met, False if timeout occurred
    """
    start_time = asyncio.get_event_loop().time()

    while True:
        try:
            result = condition()
            if asyncio.iscoroutine(result):
                result = await result
            if result:
                return True
        except (ValueError, TypeError, RuntimeError, asyncio.CancelledError):
            # Condition check failed - continue waiting
            # Catches: condition evaluation errors and cancelled coroutines
            pass

        if asyncio.get_event_loop().time() - start_time > timeout:
            return False

        await asyncio.sleep(interval)


# Global cache instance with default settings (100 items, 5 minute TTL)
_default_cache: TTLCache[str, Any] = TTLCache(maxsize=100, ttl=300)


async def async_cache_result(
    func: Callable[..., Awaitable[T]],
    cache_key: str,
    _cache_duration: float = 300.0,
    *args: Any,
    **kwargs: Any,
) -> T:
    """Cache the result of an async function call using cachetools.TTLCache.

    This function maintains backward compatibility with the original API while
    using cachetools for the underlying cache implementation.

    Args:
        func: The async function to cache
        cache_key: Unique key for caching
        _cache_duration: Cache duration in seconds (unused, uses global cache TTL)
        *args: Positional arguments to pass to the function
        **kwargs: Keyword arguments to pass to the function

    Returns:
        The cached or computed result

    Note:
        For optimal performance with varying TTLs, consider using the
        @cached_async decorator directly with a custom TTLCache instance.
    """
    # Check if we have a cached result
    if cache_key in _default_cache:
        return _default_cache[cache_key]  # type: ignore[no-any-return]

    # Compute and cache the result
    result = await func(*args, **kwargs)
    _default_cache[cache_key] = result

    return result


def cached_async(
    maxsize: int = 100, ttl: float = 300.0
) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]]:
    """Decorator to cache async function results using cachetools.TTLCache.

    This provides a cleaner alternative to async_cache_result for new code.

    Args:
        maxsize: Maximum number of items in the cache
        ttl: Time-to-live for cached items in seconds

    Returns:
        Decorator function

    Example:
        @cached_async(maxsize=50, ttl=600)
        async def expensive_operation(param: str) -> dict:
            # ... expensive async operation
            return result
    """
    cache: TTLCache[tuple[Any, ...], Any] = TTLCache(maxsize=maxsize, ttl=ttl)

    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            # Create a cache key from args and kwargs
            # Note: This assumes all arguments are hashable
            cache_key = (args, tuple(sorted(kwargs.items())))

            if cache_key in cache:
                return cache[cache_key]  # type: ignore[no-any-return]

            result = await func(*args, **kwargs)
            cache[cache_key] = result
            return result

        return wrapper

    return decorator


def parse_version(version_string: str) -> tuple[int, int, int, str]:
    """
    Parse version string into components using packaging.version.

    Handles various formats:
    - 1.2.3
    - 1.2.3-dev
    - 1.2.3.dev59+g1624e1e.d19800101
    - 0.1.dev59+g1624e1e.d19800101

    Args:
        version_string: Version string to parse

    Returns:
        Tuple of (major, minor, patch, suffix)
    """
    try:
        v = Version(version_string)

        # Extract major, minor, patch from base_version or release tuple
        release = v.release
        major = release[0] if len(release) > 0 else 0
        minor = release[1] if len(release) > 1 else 0
        patch = release[2] if len(release) > 2 else 0

        # Determine suffix based on version properties
        if v.is_devrelease:
            suffix = "dev"
        elif v.is_prerelease:
            # Handle alpha, beta, rc versions
            if v.pre:
                suffix = f"{v.pre[0]}{v.pre[1]}"
            else:
                suffix = ""
        else:
            suffix = ""

        return major, minor, patch, suffix

    except InvalidVersion:
        # Fallback for non-PEP440 versions: simple regex parsing
        import re

        match = re.match(
            r"^(\d+)(?:\.(\d+))?(?:\.(\d+))?(?:[-.]?(dev|alpha|beta|rc).*)?",
            version_string,
        )
        if match:
            major = int(match.group(1) or 0)
            minor = int(match.group(2) or 0)
            patch = int(match.group(3) or 0)
            suffix = match.group(4) or ""
            return major, minor, patch, suffix

        # Last resort: return zeros
        return 0, 0, 0, ""


def format_version(version: str, level: str) -> str:
    """Format version according to specified level.

    Args:
        version: Version string to format
        level: Format level (major, minor, patch, full, docker, npm, python)

    Returns:
        Formatted version string

    Raises:
        ValueError: If level is unknown
    """
    major, minor, patch, suffix = parse_version(version)
    base_version = f"{major}.{minor}.{patch}"

    if level == "major":
        return str(major)
    elif level == "minor":
        return f"{major}.{minor}"
    elif level == "patch" or level == "full":
        if suffix:
            return f"{base_version}-{suffix}"
        return base_version
    elif level == "docker":
        # Docker-compatible version (no + characters)
        if suffix:
            return f"{base_version}-{suffix}"
        return f"{major}.{minor}"
    elif level == "npm":
        # NPM-compatible version
        if suffix:
            return f"{base_version}-{suffix}.0"
        return base_version
    elif level == "python":
        # Python-compatible version
        if suffix:
            return f"{base_version}.{suffix}0"
        return base_version
    else:
        raise ValueError(f"Unknown version level: {level}")


def get_claude_docker_home_dir() -> str:
    """Get the Claude Docker home directory path.

    Returns:
        Path to Claude Docker home directory
    """
    import platformdirs

    claude_dir = Path(platformdirs.user_data_dir("claude"))
    claude_dir.mkdir(parents=True, exist_ok=True)

    return str(claude_dir)


def generate_schema_files(output_dir: Path | None = None) -> list[Path]:
    """Generate JSON Schema files for TOML configuration validation.

    Args:
        output_dir: Directory to write schema files to. If None, uses current directory.

    Returns:
        List of generated schema file paths

    Raises:
        ImportError: If required dependencies are not available
        OSError: If unable to write files
    """
    if output_dir is None:
        output_dir = Path.cwd()

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    generated_files: list[Path] = []

    # Generate schema for main Settings model
    schema = generate_json_schema()
    main_schema_path = output_dir / "ccproxy-schema.json"
    save_schema_file(schema, main_schema_path)
    generated_files.append(main_schema_path)

    # Generate a combined schema file that can be used for complete config validation
    combined_schema_path = output_dir / ".ccproxy-schema.json"
    save_schema_file(schema, combined_schema_path)
    generated_files.append(combined_schema_path)

    return generated_files


def generate_taplo_config(output_dir: Path | None = None) -> Path:
    """Generate taplo configuration for TOML editor support.

    Args:
        output_dir: Directory to write taplo config to. If None, uses current directory.

    Returns:
        Path to generated .taplo.toml file

    Raises:
        OSError: If unable to write file
    """
    if output_dir is None:
        output_dir = Path.cwd()

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    taplo_config_path = output_dir / ".taplo.toml"

    # Generate taplo configuration that references our schema files
    taplo_config = """# Taplo configuration for Claude Code Proxy TOML files
# This configuration enables schema validation and autocomplete in editors

[[rule]]
name = "ccproxy-config"
include = [
    ".claude_code_proxy.toml",
    "claude_code_proxy.toml",
    "config.toml",
    "**/ccproxy*.toml",
    "**/config*.toml"
]
schema = "ccproxy-schema.json"

[formatting]
# Standard TOML formatting options
indent_string = "  "
trailing_newline = true
crlf = false

[schema]
# Enable schema validation
enabled = true
# Show completions from schema
completion = true
"""

    taplo_config_path.write_text(taplo_config, encoding="utf-8")

    return taplo_config_path


def validate_config_with_schema(
    config_path: Path, schema_path: Path | None = None
) -> bool:
    """Validate a config file against the schema.

    Args:
        config_path: Path to configuration file to validate
        schema_path: Optional path to schema file. If None, generates schema from Settings

    Returns:
        True if validation passes, False otherwise

    Raises:
        ImportError: If check-jsonschema is not available
        FileNotFoundError: If config file doesn't exist
        tomllib.TOMLDecodeError: If TOML file has invalid syntax
        ValueError: For other validation errors
    """
    import subprocess
    import tempfile

    import orjson

    # Import tomllib for Python 3.11+ or fallback to tomli
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib  # type: ignore[no-redef]

    config_path = Path(config_path)

    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    # Determine the file type
    suffix = config_path.suffix.lower()

    if suffix == ".toml":
        # Read and parse TOML - let TOML parse errors bubble up
        with config_path.open("rb") as f:
            toml_data = tomllib.load(f)

        # Get or generate schema
        if schema_path:
            schema = orjson.loads(schema_path.read_bytes())
        else:
            schema = generate_json_schema()

        # Create temporary files for validation
        with tempfile.NamedTemporaryFile(
            mode="wb", suffix=".json", delete=False
        ) as schema_file:
            schema_file.write(orjson.dumps(schema, option=orjson.OPT_INDENT_2))
            temp_schema_path = schema_file.name

        with tempfile.NamedTemporaryFile(
            mode="wb", suffix=".json", delete=False
        ) as json_file:
            json_file.write(orjson.dumps(toml_data, option=orjson.OPT_INDENT_2))
            temp_json_path = json_file.name

        try:
            # Use check-jsonschema to validate
            result = subprocess.run(
                ["check-jsonschema", "--schemafile", temp_schema_path, temp_json_path],
                capture_output=True,
                text=True,
                check=False,
            )

            # Clean up temporary files
            Path(temp_schema_path).unlink(missing_ok=True)
            Path(temp_json_path).unlink(missing_ok=True)

            return result.returncode == 0

        except FileNotFoundError as e:
            # Clean up temporary files
            Path(temp_schema_path).unlink(missing_ok=True)
            Path(temp_json_path).unlink(missing_ok=True)
            raise ImportError(
                "check-jsonschema command not found. "
                "Install with: pip install check-jsonschema"
            ) from e
        except (subprocess.SubprocessError, OSError) as e:
            # Clean up temporary files in case of subprocess or file system errors
            Path(temp_schema_path).unlink(missing_ok=True)
            Path(temp_json_path).unlink(missing_ok=True)
            raise ValueError(f"Validation error: {e}") from e

    elif suffix == ".json":
        # Parse JSON to validate it's well-formed - let JSON parse errors bubble up
        orjson.loads(config_path.read_bytes())

        # Get or generate schema
        if schema_path:
            temp_schema_path = str(schema_path)
            cleanup_schema = False
        else:
            schema = generate_json_schema()
            with tempfile.NamedTemporaryFile(
                mode="wb", suffix=".json", delete=False
            ) as schema_file:
                schema_file.write(orjson.dumps(schema, option=orjson.OPT_INDENT_2))
                temp_schema_path = schema_file.name
                cleanup_schema = True

        try:
            result = subprocess.run(
                [
                    "check-jsonschema",
                    "--schemafile",
                    temp_schema_path,
                    str(config_path),
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            if cleanup_schema:
                Path(temp_schema_path).unlink(missing_ok=True)

            return result.returncode == 0

        except FileNotFoundError as e:
            if cleanup_schema:
                Path(temp_schema_path).unlink(missing_ok=True)
            raise ImportError(
                "check-jsonschema command not found. "
                "Install with: pip install check-jsonschema"
            ) from e
        except (subprocess.SubprocessError, OSError) as e:
            # Subprocess or file system errors during validation
            if cleanup_schema:
                Path(temp_schema_path).unlink(missing_ok=True)
            raise ValueError(f"Validation error: {e}") from e

    else:
        raise ValueError(
            f"Unsupported config file format: {suffix}. Only TOML (.toml) files are supported."
        )


def generate_json_schema() -> dict[str, Any]:
    """Generate JSON Schema from Settings model.

    Returns:
        JSON Schema dictionary

    Raises:
        ImportError: If required dependencies are not available
    """
    try:
        from claude_code_proxy.config.settings import Settings
    except ImportError as e:
        raise ImportError(f"Required dependencies not available: {e}") from e

    schema = Settings.model_json_schema()

    # Add schema metadata
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["title"] = "CCProxy API Configuration"

    # Add examples for common properties
    properties = schema.get("properties", {})
    if "host" in properties:
        properties["host"]["examples"] = ["127.0.0.1", "0.0.0.0", "localhost"]  # nosec B104
    if "port" in properties:
        properties["port"]["examples"] = [8000, 8080, 3000]
    if "log_level" in properties:
        properties["log_level"]["examples"] = ["DEBUG", "INFO", "WARNING", "ERROR"]
    if "cors_origins" in properties:
        properties["cors_origins"]["examples"] = [
            ["*"],
            ["https://example.com", "https://app.example.com"],
            ["http://localhost:3000"],
        ]

    return schema


def save_schema_file(schema: dict[str, Any], output_path: Path) -> None:
    """Save JSON Schema to a file.

    Args:
        schema: JSON Schema dictionary to save
        output_path: Path to write schema file to

    Raises:
        OSError: If unable to write file
    """
    import orjson

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    output_path.write_bytes(orjson.dumps(schema, option=orjson.OPT_INDENT_2))
