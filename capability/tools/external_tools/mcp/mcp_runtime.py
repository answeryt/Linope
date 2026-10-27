# -*- coding: utf-8 -*-
"""Host that wires the MCP plugins for one process.

The plugins do not import each other. This module loads them by file path,
connects the servers in the project list, and registers their tools.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import threading
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


_DIR = Path(__file__).resolve().parent
_FIRECRAWL_HOST = "mcp.firecrawl.dev"
_FIRECRAWL_KEY = "FIRECRAWL_API_KEY"

_MODULES: dict[str, Any] = {}
_RUNTIME: "MCPRuntime | None" = None
_LOCK = threading.Lock()


def call(manager: Any, name: str, arguments: dict[str, Any]) -> str:
    """Connect configured servers if needed, then call one registered tool."""
    return _runtime().call(manager, name, arguments)


class MCPRuntime:
    """One process-wide connection owner."""

    def __init__(self) -> None:
        self._bridge: Any = None
        self._host: Any = None
        self._content: Any = None
        self._client_cls: Any = None
        self._protocol_cls: Any = None

    def call(self, manager: Any, name: str, arguments: dict[str, Any]) -> str:
        """Open each configured server on the host loop and call one tool there.

        The session is used by the same task that opens it. A later task on
        that loop cannot safely call into a session the host manager is holding.
        """
        self._load()
        if self._bridge is None:
            host_mod = _plugin("linope_mcp_host", "mcp_host_manager_plugin.py")
            self._bridge = host_mod.MCPHostThreadBridge()
            self._host = host_mod.MCPHostManagerPlugin()
        return self._bridge.run(
            self._serve(manager, name, arguments),
            timeout=180.0,
        )

    def _load(self) -> None:
        if self._client_cls is not None:
            return
        self._client_cls = _plugin("linope_mcp_client", "mcp_client.py").MCPClient
        self._protocol_cls = _plugin(
            "linope_mcp_protocol",
            "mcp_protocol_plugin.py",
        ).MCPProtocolPlugin
        self._content = _plugin(
            "linope_mcp_content",
            "mcp_content_plugin.py",
        ).MCPContentPlugin()

    async def _serve(self, manager: Any, name: str, arguments: dict[str, Any]) -> str:
        config_mod = _plugin("linope_mcp_config", "mcp_config_plugin.py")
        servers = list(config_mod.MCPConfigPlugin().project_servers().values())
        rendered: dict[str, Any] | None = None
        for server in servers:
            prepared = _prepare(server.to_dict())
            include, exclude = _tool_filter(server.tools)
            timeout = max(float(server.connect_timeout), float(server.tool_timeout)) + 30.0

            async def discover(session: Any, server=server, include=include, exclude=exclude):
                protocol = self._protocol_cls(session)
                tools = await protocol.list_tools()
                records = manager.register_server_tools(
                    server.name,
                    tools,
                    include=include,
                    exclude=exclude,
                )
                record = next((item for item in records if item.name == name), None)
                if record is None:
                    return None
                client = self._client_cls(server.name, session)
                result = await client.call_tool(record.remote_name, arguments)
                return self._content.render_tool_result(result, server_name=server.name)

            outcome = await self._host.probe(
                _factory(prepared),
                discover=discover,
                timeout=timeout,
            )
            if outcome is not None:
                rendered = outcome
                break
        if rendered is None:
            known = ", ".join(record.name for record in manager.records()) or "none"
            raise LookupError(f"MCP tool {name!r} is not on a connected server. Available: {known}")
        if "error" in rendered and "result" not in rendered:
            rendered = {"success": False, **rendered}
        else:
            rendered = {"success": True, **rendered}
        return json.dumps(rendered, ensure_ascii=False)


def _factory(config: dict[str, Any]):
    transport = str(config.get("transport") or "stdio")
    module = _transport(transport)

    def factory():
        return module.MCPClientConnect(config).open()

    return factory


def _transport(name: str) -> Any:
    if name == "sse":
        return _plugin("linope_mcp_sse", "mcp_transport/sse.py")
    if name == "stdio":
        return _plugin("linope_mcp_stdio", "mcp_transport/stdio.py")
    if name == "streamable_http":
        return _plugin("linope_mcp_http", "mcp_transport/streamable_http.py")
    raise RuntimeError(f"No such MCP transport: {name}")


def _prepare(config: dict[str, Any]) -> dict[str, Any]:
    """Attach the Firecrawl key when the official URL has no Authorization."""
    prepared = dict(config)
    url = str(prepared.get("url") or "")
    host = (urlparse(url).hostname or "").lower()
    if host != _FIRECRAWL_HOST:
        return prepared
    headers = {
        str(key): str(value)
        for key, value in dict(prepared.get("headers") or {}).items()
    }
    if any(key.lower() == "authorization" for key in headers):
        return prepared
    secret = _secret(_FIRECRAWL_KEY)
    if not secret:
        return prepared
    headers["Authorization"] = f"Bearer {secret}"
    prepared["headers"] = headers
    return prepared


def _tool_filter(tools: dict[str, Any]) -> tuple[Any, Any]:
    include = tools.get("include", tools.get("enable"))
    exclude = tools.get("exclude", tools.get("disable"))
    return include, exclude


def _secret(name: str) -> str | None:
    from kernel.environment import current_room

    room = current_room()
    if room is not None:
        try:
            value = room.identity.resolve_secret(name)
        except RuntimeError:
            value = ""
        if str(value or "").strip():
            return str(value).strip()
    value = os.environ.get(name) or ""
    return value.strip() or None


def _runtime() -> MCPRuntime:
    global _RUNTIME
    with _LOCK:
        if _RUNTIME is None:
            _RUNTIME = MCPRuntime()
        return _RUNTIME


def _plugin(name: str, relative: str) -> Any:
    cached = _MODULES.get(name)
    if cached is not None:
        return cached
    path = _DIR / relative
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot open the MCP plugin: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(name, None)
        raise
    _MODULES[name] = module
    return module
