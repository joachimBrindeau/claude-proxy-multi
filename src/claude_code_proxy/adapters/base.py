"""Base adapter abstractions for API format conversion.

This module provides the canonical definition of the APIAdapter interface.
All adapter implementations should inherit from this base class.
"""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any


__all__ = [
    "APIAdapter",
]


class APIAdapter(ABC):
    """Abstract base class for API format adapters.

    Provides interface for converting between different API formats (e.g., OpenAI <-> Anthropic).
    Implementations should provide methods for request, response, and stream adaptation.
    """

    @abstractmethod
    def adapt_request(self, request: dict[str, Any]) -> dict[str, Any]:
        """Convert a request from one API format to another.

        Args:
            request: The request data to convert

        Returns:
            The converted request data

        Raises:
            ValueError: If the request format is invalid or unsupported
        """
        pass

    @abstractmethod
    def adapt_response(self, response: dict[str, Any]) -> dict[str, Any]:
        """Convert a response from one API format to another.

        Args:
            response: The response data to convert

        Returns:
            The converted response data

        Raises:
            ValueError: If the response format is invalid or unsupported
        """
        pass

    @abstractmethod
    def adapt_stream(
        self, stream: AsyncIterator[dict[str, Any]]
    ) -> AsyncIterator[dict[str, Any]]:
        """Convert a streaming response from one API format to another.

        Args:
            stream: The streaming response data to convert

        Yields:
            The converted streaming response chunks

        Raises:
            ValueError: If the stream format is invalid or unsupported
        """
        # This should be implemented as an async generator
        # async def adapt_stream(self, stream): ...
        #     async for item in stream:
        #         yield transformed_item
        raise NotImplementedError
