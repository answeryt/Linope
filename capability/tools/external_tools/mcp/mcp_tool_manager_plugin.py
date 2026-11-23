# -*- coding: utf-8 -*-
"""One tool process that calls the local MCPHub.

MCPHub owns the server connections. This plugin only lists and calls the
tools that hub is already serving.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


PLUGIN_NAME = "mcp_tool_manager"
PLUGIN_VERSION = "1.0"
_DEFAULT_URL = "http://127.0.0.1:3000/mcp"
_HUB_FILE = Path(__file__).resolve().with_name("hub.json")


def load(kind, body, call_params=None):
    """Load one tool call. ``list`` returns the tools MCPHub is serving."""

    del call_params
    return asyncio.run(_load(kind, body))


async def load_async(kind, body, call_params=None):
    """Same as ``load`` on the process event loop."""

    del call_params
    return await _load(kind, body)


def capability_profile(capability_id, changes):
    """This process leases a tool resource. MCPHub is outside the kernel."""

    del changes
    from kernel.process.declaration import ProcessDeclaration, ResourceClaim
    from kernel.resource.definition import ResourceKind

    return ProcessDeclaration(
        capability=capability_id,
        resources=(
            ResourceClaim(kind=ResourceKind.TOOL, identity={"id": capability_id}),
        ),
    )


def hub_url() -> str:
    """The Streamable HTTP endpoint written beside this plugin."""

    try:
        payload = json.loads(_HUB_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _DEFAULT_URL
    if not isinstance(payload, dict):
        return _DEFAULT_URL
    url = str(payload.get("url") or "").strip()
    return url or _DEFAULT_URL


async def _load(kind, body) -> str:
    name, arguments = _tool_call(kind, body)
    url = hub_url()
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(30, read=300),
            follow_redirects=True,
            trust_env=False,
        ) as client:
            async with streamable_http_client(url, http_client=client) as (
                read,
                write,
                _session_id,
            ):
                return await _use_session(session_streams=(read, write), name=name, arguments=arguments)
    except Exception as exc:
        if _hub_down(exc):
            raise RuntimeError(f"MCPHub is not running at {url}") from exc
        raise


async def _use_session(session_streams, name: str, arguments: dict[str, Any]) -> str:
    read, write = session_streams
    async with ClientSession(read, write) as session:
        await session.initialize()
        if not name or name == "list":
            return json.dumps(
                {"success": True, "tools": await _schemas(session)},
                ensure_ascii=False,
            )
        result = await session.call_tool(name, arguments)
    if getattr(result, "isError", False):
        text = _content_text(result)
        raise RuntimeError(text or f"MCP tool failed: {name}")
    return _content_text(result)


async def _schemas(session: ClientSession) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    cursor: str | None = None
    while True:
        page = await session.list_tools(cursor)
        for tool in page.tools:
            schema = getattr(tool, "inputSchema", None)
            if not isinstance(schema, dict) or not schema:
                schema = {"type": "object", "properties": {}}
            found.append({
                "name": str(tool.name),
                "description": str(getattr(tool, "description", "") or ""),
                "parameters": schema,
            })
        cursor = getattr(page, "nextCursor", None)
        if not cursor:
            return found


def _tool_call(kind, body) -> tuple[str, dict[str, Any]]:
    if kind != "tool":
        raise ValueError(f"This process cannot load {kind}")
    if isinstance(body, str):
        body = {"name": body}
    if body is None:
        body = {}
    if not isinstance(body, dict):
        raise TypeError("tool content must be a mapping")
    arguments = body.get("arguments") or {}
    if not isinstance(arguments, dict):
        raise TypeError("arguments must be a mapping")
    return str(body.get("name") or ""), dict(arguments)


def _content_text(result: Any) -> str:
    parts: list[str] = []
    for block in getattr(result, "content", ()) or ():
        text = getattr(block, "text", None)
        if text:
            parts.append(str(text))
    if parts:
        return "\n".join(parts)
    structured = getattr(result, "structuredContent", None)
    if structured is not None:
        return json.dumps(structured, ensure_ascii=False)
    return ""


def _hub_down(exc: BaseException) -> bool:
    if isinstance(exc, (ConnectionError, TimeoutError, OSError)):
        return True
    name = type(exc).__name__
    if name in {
        "ConnectError",
        "ConnectTimeout",
        "ReadTimeout",
        "NetworkError",
        "HTTPStatusError",
        "RemoteProtocolError",
    }:
        return True
    nested = getattr(exc, "exceptions", None)
    if isinstance(nested, tuple) and nested:
        return any(_hub_down(item) for item in nested)
    return False
