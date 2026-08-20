# -*- coding: utf-8 -*-
"""Standalone SSE MCP connection plugin.

This module owns one SSE connection attempt. It imports no sibling project
module and can be loaded directly from its file path.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Mapping, TextIO
from urllib.parse import urlparse

import httpx
from mcp import ClientSession

try:
    from mcp.client.sse import sse_client
except ImportError:  # pragma: no cover - compatibility with older MCP SDKs
    sse_client = None

try:
    from mcp.types import LATEST_PROTOCOL_VERSION
except ImportError:  # pragma: no cover - compatibility fallback
    LATEST_PROTOCOL_VERSION = "2025-03-26"


TRANSPORT = "sse"


class InvalidMCPConfiguration(ValueError):
    """Raised when an SSE MCP configuration is invalid."""


class MCPClientConnect:
    """Open and initialize one MCP session over SSE."""

    def __init__(
        self,
        config: Mapping[str, Any],
        *,
        session_kwargs: Mapping[str, Any] | None = None,
        errlog: TextIO | None = None,
    ) -> None:
        self.config = dict(config)
        self.session_kwargs = dict(session_kwargs or {})
        self.errlog = errlog
        self.initialize_result: Any = None

        parsed = urlparse(str(self.config.get("url", "")))
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise InvalidMCPConfiguration(
                "SSE MCP URL must be an absolute http:// or https:// URL.",
            )

    @property
    def transport(self) -> str:
        """Return the transport implemented by this plugin."""
        return TRANSPORT

    def _http_headers(self) -> dict[str, str]:
        headers = {
            str(key): str(value)
            for key, value in dict(self.config.get("headers") or {}).items()
        }
        if not any(key.lower() == "mcp-protocol-version" for key in headers):
            headers["MCP-Protocol-Version"] = LATEST_PROTOCOL_VERSION
        return headers

    def _http_client_kwargs(
        self,
        headers: dict[str, str],
    ) -> dict[str, Any]:
        connect_timeout = float(self.config.get("connect_timeout", 60.0))
        read_timeout = float(self.config.get("read_timeout", 300.0))
        original_url = httpx.URL(str(self.config["url"]))

        async def strip_cross_origin_authorization(response: httpx.Response) -> None:
            if not response.is_redirect or response.next_request is None:
                return
            target = response.next_request.url
            if (target.scheme, target.host, target.port) != (
                original_url.scheme,
                original_url.host,
                original_url.port,
            ):
                response.next_request.headers.pop("Authorization", None)

        kwargs: dict[str, Any] = {
            "headers": headers or None,
            "follow_redirects": True,
            "timeout": httpx.Timeout(connect_timeout, read=read_timeout),
            "verify": self.config.get("ssl_verify", True),
            "event_hooks": {"response": [strip_cross_origin_authorization]},
        }
        if self.config.get("auth") is not None:
            kwargs["auth"] = self.config["auth"]
        if self.config.get("client_cert") is not None:
            kwargs["cert"] = self.config["client_cert"]
        return kwargs

    @asynccontextmanager
    async def _initialized_session(
        self,
        read_stream: Any,
        write_stream: Any,
    ) -> AsyncIterator[ClientSession]:
        async with ClientSession(
            read_stream,
            write_stream,
            **self.session_kwargs,
        ) as session:
            connect_timeout = float(self.config.get("connect_timeout", 60.0))
            self.initialize_result = await asyncio.wait_for(
                session.initialize(),
                timeout=connect_timeout,
            )
            yield session

    @asynccontextmanager
    async def open(self) -> AsyncIterator[ClientSession]:
        """Open and initialize exactly one SSE MCP session."""
        self.initialize_result = None
        if sse_client is None:
            raise ImportError(
                "The installed MCP SDK does not provide SSE transport.",
            )

        headers = self._http_headers()
        connect_timeout = float(self.config.get("connect_timeout", 60.0))
        read_timeout = float(self.config.get("read_timeout", 300.0))
        kwargs: dict[str, Any] = {
            "url": str(self.config["url"]),
            "headers": headers or None,
            "timeout": connect_timeout,
            "sse_read_timeout": read_timeout,
        }
        if self.config.get("auth") is not None:
            kwargs["auth"] = self.config["auth"]
        if (
            self.config.get("client_cert") is not None
            or self.config.get("ssl_verify", True) is not True
        ):
            client_kwargs = self._http_client_kwargs(headers)

            def client_factory(headers=None, timeout=None, auth=None):
                configured = dict(client_kwargs)
                if headers is not None:
                    configured["headers"] = headers
                if timeout is not None:
                    configured["timeout"] = timeout
                if auth is not None:
                    configured["auth"] = auth
                return httpx.AsyncClient(**configured)

            kwargs["httpx_client_factory"] = client_factory

        async with sse_client(**kwargs) as streams:
            async with self._initialized_session(*streams) as session:
                yield session
