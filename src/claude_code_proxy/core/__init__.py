"""Core abstractions for the CCProxy API."""

from claude_code_proxy.adapters.base import APIAdapter
from claude_code_proxy.auth.storage.base import TokenStorage
from claude_code_proxy.core.async_utils import (
    async_cache_result,
    async_timer,
    cached_async,
    gather_with_concurrency,
    get_package_dir,
    get_root_package_name,
    patched_typing,
    run_in_executor,
    safe_await,
    wait_for_condition,
)
from claude_code_proxy.core.constants import (
    ANTHROPIC_API_BASE_PATH,
    AUTH_HEADER,
    CHAT_COMPLETIONS_ENDPOINT,
    CONFIG_FILE_NAMES,
    CONTENT_TYPE_HEADER,
    CONTENT_TYPE_JSON,
    CONTENT_TYPE_STREAM,
    CONTENT_TYPE_TEXT,
    DEFAULT_DOCKER_IMAGE,
    DEFAULT_DOCKER_TIMEOUT,
    DEFAULT_MAX_TOKENS,
    DEFAULT_MODEL,
    DEFAULT_RATE_LIMIT,
    DEFAULT_STREAM,
    DEFAULT_TEMPERATURE,
    DEFAULT_TIMEOUT,
    DEFAULT_TOP_P,
    ERROR_MSG_INTERNAL_ERROR,
    ERROR_MSG_INVALID_REQUEST,
    ERROR_MSG_INVALID_TOKEN,
    ERROR_MSG_MODEL_NOT_FOUND,
    ERROR_MSG_RATE_LIMIT_EXCEEDED,
    JSON_EXTENSIONS,
    LOG_LEVELS,
    MESSAGES_ENDPOINT,
    MODELS_ENDPOINT,
    OPENAI_API_BASE_PATH,
    REQUEST_ID_HEADER,
    STATUS_BAD_REQUEST,
    STATUS_INTERNAL_ERROR,
    STATUS_NOT_FOUND,
    STATUS_OK,
    STATUS_RATE_LIMITED,
    STATUS_SERVICE_UNAVAILABLE,
    STATUS_UNAUTHORIZED,
    STREAM_EVENT_CONTENT_BLOCK_DELTA,
    STREAM_EVENT_CONTENT_BLOCK_START,
    STREAM_EVENT_CONTENT_BLOCK_STOP,
    STREAM_EVENT_MESSAGE_DELTA,
    STREAM_EVENT_MESSAGE_START,
    STREAM_EVENT_MESSAGE_STOP,
    TOML_EXTENSIONS,
    YAML_EXTENSIONS,
)
from claude_code_proxy.core.http import (
    BaseProxyClient,
    HTTPClient,
    HTTPConnectionError,
    HTTPError,
    HTTPTimeoutError,
    HTTPXClient,
)
from claude_code_proxy.core.transformers import (
    BaseTransformer,
    ChainedTransformer,
    RequestTransformer,
    ResponseTransformer,
    TransformerProtocol,
)
from claude_code_proxy.core.transformers import (
    RequestTransformer as IRequestTransformer,
)
from claude_code_proxy.core.transformers import (
    ResponseTransformer as IResponseTransformer,
)
from claude_code_proxy.core.transformers import (
    TransformerProtocol as ITransformerProtocol,
)
from claude_code_proxy.core.types import (
    MiddlewareConfig,
    ProxyConfig,
    ProxyMethod,
    ProxyRequest,
    ProxyResponse,
    TransformContext,
)
from claude_code_proxy.core.types import (
    ProxyProtocol as ProxyProtocolEnum,
)
from claude_code_proxy.core.validators import (
    EmailStr,
    HttpUrl,
    NonEmptyStr,
    Port,
    PositiveTimeout,
    ValidationError,
    parse_comma_separated,
    validate_path,
)
from claude_code_proxy.exceptions import (
    AuthenticationError as ProxyAuthenticationError,
)
from claude_code_proxy.exceptions import (
    CCProxyError as MiddlewareError,
)
from claude_code_proxy.exceptions import (
    CCProxyError as ProxyError,
)
from claude_code_proxy.exceptions import (
    CCProxyError as TransformationError,
)
from claude_code_proxy.exceptions import (
    HTTPConnectionError as ProxyConnectionError,
)
from claude_code_proxy.exceptions import (
    HTTPTimeoutError as ProxyTimeoutError,
)


__all__ = [
    # HTTP client abstractions
    "HTTPClient",
    "BaseProxyClient",
    "HTTPError",
    "HTTPTimeoutError",
    "HTTPConnectionError",
    "HTTPXClient",
    # Interface abstractions
    "APIAdapter",
    "IRequestTransformer",
    "IResponseTransformer",
    "TokenStorage",
    "ITransformerProtocol",
    # Transformer abstractions
    "BaseTransformer",
    "RequestTransformer",
    "ResponseTransformer",
    "TransformerProtocol",
    "ChainedTransformer",
    # Error types
    "ProxyError",
    "TransformationError",
    "MiddlewareError",
    "ProxyConnectionError",
    "ProxyTimeoutError",
    "ProxyAuthenticationError",
    "ValidationError",
    # Type definitions
    "ProxyRequest",
    "ProxyResponse",
    "TransformContext",
    "ProxyMethod",
    "ProxyProtocolEnum",
    "ProxyConfig",
    "MiddlewareConfig",
    # Async utilities
    "async_cache_result",
    "async_timer",
    "cached_async",
    "gather_with_concurrency",
    "get_package_dir",
    "get_root_package_name",
    "patched_typing",
    "run_in_executor",
    "safe_await",
    "wait_for_condition",
    # Constants
    "ANTHROPIC_API_BASE_PATH",
    "AUTH_HEADER",
    "CHAT_COMPLETIONS_ENDPOINT",
    "CONFIG_FILE_NAMES",
    "CONTENT_TYPE_HEADER",
    "CONTENT_TYPE_JSON",
    "CONTENT_TYPE_STREAM",
    "CONTENT_TYPE_TEXT",
    "DEFAULT_DOCKER_IMAGE",
    "DEFAULT_DOCKER_TIMEOUT",
    "DEFAULT_MAX_TOKENS",
    "DEFAULT_MODEL",
    "DEFAULT_RATE_LIMIT",
    "DEFAULT_STREAM",
    "DEFAULT_TEMPERATURE",
    "DEFAULT_TIMEOUT",
    "DEFAULT_TOP_P",
    "ERROR_MSG_INTERNAL_ERROR",
    "ERROR_MSG_INVALID_REQUEST",
    "ERROR_MSG_INVALID_TOKEN",
    "ERROR_MSG_MODEL_NOT_FOUND",
    "ERROR_MSG_RATE_LIMIT_EXCEEDED",
    "JSON_EXTENSIONS",
    "LOG_LEVELS",
    "MESSAGES_ENDPOINT",
    "MODELS_ENDPOINT",
    "OPENAI_API_BASE_PATH",
    "REQUEST_ID_HEADER",
    "STATUS_BAD_REQUEST",
    "STATUS_INTERNAL_ERROR",
    "STATUS_NOT_FOUND",
    "STATUS_OK",
    "STATUS_RATE_LIMITED",
    "STATUS_SERVICE_UNAVAILABLE",
    "STATUS_UNAUTHORIZED",
    "STREAM_EVENT_CONTENT_BLOCK_DELTA",
    "STREAM_EVENT_CONTENT_BLOCK_START",
    "STREAM_EVENT_CONTENT_BLOCK_STOP",
    "STREAM_EVENT_MESSAGE_DELTA",
    "STREAM_EVENT_MESSAGE_START",
    "STREAM_EVENT_MESSAGE_STOP",
    "TOML_EXTENSIONS",
    "YAML_EXTENSIONS",
    # Validators - Pydantic types
    "EmailStr",
    "HttpUrl",
    "Port",
    "PositiveTimeout",
    "NonEmptyStr",
    "ValidationError",
    # Validators - Utility functions
    "parse_comma_separated",
    "validate_path",
]
