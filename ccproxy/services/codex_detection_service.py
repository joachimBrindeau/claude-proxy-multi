"""Service for automatically detecting Codex CLI headers at startup."""

from __future__ import annotations

import asyncio
import json
import os
import socket
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import structlog
from fastapi import FastAPI, Request, Response

from ccproxy.config.discovery import get_ccproxy_cache_dir
from ccproxy.config.settings import Settings
from ccproxy.models.detection import (
    CodexCacheData,
    CodexHeaders,
    CodexInstructionsData,
)


logger = structlog.get_logger(__name__)


class CodexDetectionService:
    """Service for automatically detecting Codex CLI headers at startup."""

    def __init__(self, settings: Settings) -> None:
        """Initialize Codex detection service."""
        self.settings = settings
        self.cache_dir = get_ccproxy_cache_dir()
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._cached_data: CodexCacheData | None = None

    async def initialize_detection(self) -> CodexCacheData:
        """Initialize Codex detection at startup."""
        try:
            # Get current Codex version
            current_version = await self._get_codex_version()

            # Try to load from cache first
            detected_data = self._load_from_cache(current_version)
            cached = detected_data is not None
            if cached:
                logger.debug("detection_codex_headers_debug", version=current_version)
            else:
                # No cache or version changed - detect fresh
                detected_data = await self._detect_codex_headers(current_version)
                # Cache the results
                self._save_to_cache(detected_data)

            self._cached_data = detected_data

            logger.info(
                "detection_codex_headers_completed",
                version=current_version,
                cached=cached,
            )

            # TODO: add proper testing without codex cli installed
            if detected_data is None:
                raise ValueError("Codex detection failed")
            return detected_data

        except Exception as e:
            logger.warning("detection_codex_headers_failed", fallback=True, error=e)
            # Return fallback data
            fallback_data = self._get_fallback_data()
            self._cached_data = fallback_data
            return fallback_data

    def get_cached_data(self) -> CodexCacheData | None:
        """Get currently cached detection data."""
        return self._cached_data

    async def _get_codex_version(self) -> str:
        """Get Codex CLI version."""
        try:
            result = subprocess.run(
                ["codex", "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                # Extract version from output like "codex 0.21.0"
                version_line = result.stdout.strip()
                if " " in version_line:
                    # Handle "codex 0.21.0" format - extract just the version number
                    return version_line.split()[-1]
                return version_line
            else:
                raise RuntimeError(f"Codex version command failed: {result.stderr}")

        except (subprocess.TimeoutExpired, FileNotFoundError, RuntimeError) as e:
            logger.warning("codex_version_detection_failed", error=str(e))
            return "unknown"

    async def _detect_codex_headers(self, version: str) -> CodexCacheData:
        """Execute Codex CLI with proxy to capture headers and instructions."""
        # Data captured from the request
        captured_data: dict[str, Any] = {}

        async def capture_handler(request: Request) -> Response:
            """Capture the Codex CLI request."""
            captured_data["headers"] = dict(request.headers)
            captured_data["body"] = await request.body()
            # Return a mock response to satisfy Codex CLI
            return Response(
                content='{"choices": [{"message": {"content": "Test response"}}]}',
                media_type="application/json",
                status_code=200,
            )

        # Create temporary FastAPI app
        temp_app = FastAPI()
        temp_app.post("/backend-api/codex/responses")(capture_handler)

        # Find available port
        sock = socket.socket()
        sock.bind(("", 0))
        port = sock.getsockname()[1]
        sock.close()

        # Start server in background
        from uvicorn import Config, Server

        config = Config(temp_app, host="127.0.0.1", port=port, log_level="error")
        server = Server(config)

        logger.debug("start")
        server_task = asyncio.create_task(server.serve())

        try:
            # Wait for server to start
            await asyncio.sleep(0.5)

            # Execute Codex CLI with proxy
            env = {
                **dict(os.environ),
                "OPENAI_BASE_URL": f"http://127.0.0.1:{port}/backend-api/codex",
            }

            process = await asyncio.create_subprocess_exec(
                "codex",
                "exec",
                "test",
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            # stderr = ""
            # if process.stderr:
            #     stderr = await process.stderr.read(128)
            # stdout = ""
            # if process.stdout:
            #     stdout = await process.stdout.read(128)
            # logger.warning("rcecdy", stderr=stderr, stdout=stdout)

            # Wait for process with timeout
            try:
                await asyncio.wait_for(process.wait(), timeout=300)
            except TimeoutError:
                process.kill()
                await process.wait()

            # Stop server
            server.should_exit = True
            await server_task

            if not captured_data:
                raise RuntimeError("Failed to capture Codex CLI request")

            # Extract headers and instructions
            headers = self._extract_headers(captured_data["headers"])
            instructions = self._extract_instructions(captured_data["body"])

            return CodexCacheData(
                codex_version=version,
                headers=headers,
                instructions=instructions,
                cached_at=datetime.now(UTC),
            )

        except Exception as e:
            # Ensure server is stopped
            server.should_exit = True
            if not server_task.done():
                await server_task
            raise

    def _load_from_cache(self, version: str) -> CodexCacheData | None:
        """Load cached data for specific Codex version."""
        cache_file = self.cache_dir / f"codex_headers_{version}.json"

        if not cache_file.exists():
            return None

        try:
            with cache_file.open("r") as f:
                data = json.load(f)
                return CodexCacheData.model_validate(data)
        except Exception:
            return None

    def _save_to_cache(self, data: CodexCacheData) -> None:
        """Save detection data to cache."""
        cache_file = self.cache_dir / f"codex_headers_{data.codex_version}.json"

        try:
            with cache_file.open("w") as f:
                json.dump(data.model_dump(), f, indent=2, default=str)
            logger.debug(
                "cache_saved", file=str(cache_file), version=data.codex_version
            )
        except Exception as e:
            logger.warning("cache_save_failed", file=str(cache_file), error=str(e))

    def _extract_headers(self, headers: dict[str, str]) -> CodexHeaders:
        """Extract Codex CLI headers from captured request."""
        try:
            return CodexHeaders.model_validate(headers)
        except Exception as e:
            logger.error("header_extraction_failed", error=str(e))
            raise ValueError(f"Failed to extract required headers: {e}") from e

    def _extract_instructions(self, body: bytes) -> CodexInstructionsData:
        """Extract instructions from captured request body."""
        try:
            data = json.loads(body.decode("utf-8"))
            instructions_content = data.get("instructions")

            if instructions_content is None:
                raise ValueError("No instructions field found in request body")

            return CodexInstructionsData(instructions_field=instructions_content)

        except Exception as e:
            logger.error("instructions_extraction_failed", error=str(e))
            raise ValueError(f"Failed to extract instructions: {e}") from e

    def _get_fallback_data(self) -> CodexCacheData:
        """Get fallback data when detection fails."""
        logger.warning("using_fallback_codex_data")

        # Load fallback data from package data file
        package_data_file = (
            Path(__file__).parent.parent / "data" / "codex_headers_fallback.json"
        )
        with package_data_file.open("r") as f:
            fallback_data_dict = json.load(f)
            return CodexCacheData.model_validate(fallback_data_dict)
