# -*- coding: utf-8 -*-
"""Standalone Streamable HTTP MCP connection plugin.

This module owns one Streamable HTTP connection attempt. It imports no sibling
project module and can be loaded directly from its file path.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Mapping, TextIO
from urllib.parse import urlparse

import httpx
from mcp import ClientSession

try:
    from mcp.client.streamable_http import streamable_http_client
except ImportError:  # pragma: no cover - compatibility with older MCP SDKs
    streamable_http_client = None

try:
    from mcp.types import LATEST_PROTOCOL_VERSION
except ImportError:  # pragma: no cover - compatibility fallback
    LATEST_PROTOCOL_VERSION = "2025-03-26"


TRANSPORT = "streamable_http"


class InvalidMCPConfiguration(ValueError):
    """Raised when a Streamable HTTP MCP configuration is invalid."""


class NonMCPEndpointError(ConnectionError):
    """Raised when an HTTP URL clearly points to a non-MCP endpoint."""


class MCPClientConnect:
    """Open and initialize one MCP session over Streamable HTTP."""

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
                "Streamable HTTP MCP URL must be an absolute "
                "http:// or https:// URL.",
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
        *,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        connect_timeout = float(
            timeout
            if timeout is not None
            else self.config.get("connect_timeout", 60.0),
        )
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

    async def _preflight_http(
        self,
        url: str,
        headers: dict[str, str],
    ) -> None:
        """Reject an unambiguous HTML/non-MCP endpoint before SDK startup."""
        if self.config.get("skip_preflight") or self.config.get("auth"):
            return
        timeout = float(self.config.get("preflight_timeout", 5.0))
        kwargs = self._http_client_kwargs(headers, timeout=timeout)
        kwargs.pop("event_hooks", None)
        try:
            async with httpx.AsyncClient(**kwargs) as client:
                response = await client.head(url)
                if response.status_code in {405, 501}:
                    response = await client.get(url)
                content_type = (
                    response.headers.get("content-type", "")
                    .split(";", 1)[0]
                    .strip()
                    .lower()
                )
                if (
                    200 <= response.status_code < 300
                    and content_type
                    and content_type not in {"application/json", "text/event-stream"}
                ):
                    probe = await client.post(
                        url,
                        headers={
                            **headers,
                            "Content-Type": "application/json",
                            "Accept": "application/json, text/event-stream",
                        },
                        json={
                            "jsonrpc": "2.0",
                            "id": "_probe",
                            "method": "initialize",
                            "params": {
                                "protocolVersion": LATEST_PROTOCOL_VERSION,
                                "capabilities": {},
                                "clientInfo": {
                                    "name": "standalone-mcp-probe",
                                    "version": "1.0",
                                },
                            },
                        },
                    )
                    probe_type = (
                        probe.headers.get("content-type", "")
                        .split(";", 1)[0]
                        .strip()
                        .lower()
                    )
                    if not (
                        200 <= probe.status_code < 300
                        and probe_type in {"application/json", "text/event-stream"}
                    ):
                        raise NonMCPEndpointError(
                            f"{url!r} returned {content_type!r}, "
                            "not an MCP response.",
                        )
        except httpx.HTTPError:
            # The real MCP handshake remains the source of truth for network,
            # authentication, and transient endpoint failures.
            return

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
        """Open and initialize exactly one Streamable HTTP MCP session."""
        self.initialize_result = None
        if streamable_http_client is None:
            raise ImportError(
                "The installed MCP SDK does not provide "
                "streamable_http_client.",
            )

        url = str(self.config["url"])
        headers = self._http_headers()
        await self._preflight_http(url, headers)
        async with httpx.AsyncClient(
            **self._http_client_kwargs(headers),
        ) as http_client:
            async with streamable_http_client(
                url,
                http_client=http_client,
            ) as streams:
                async with self._initialized_session(
                    streams[0],
                    streams[1],
                ) as session:
                    yield session
