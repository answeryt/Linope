# -*- coding: utf-8 -*-
"""Core MCP client implementation.

The connection lifecycle is intentionally outside this module. Callers provide
an initialized :class:`mcp.ClientSession`; this client only exposes MCP tool
discovery, lookup, filtering, and invocation.
"""
import re
from typing import Any

import mcp.types
from mcp import ClientSession


class MCPClient:
    """Operate on an initialized MCP session.

    Transport creation, connection state, session initialization, shutdown,
    retries, caching, refresh, and timeouts belong to other components.
    """

    def __init__(
        self,
        name: str,
        session: ClientSession,
        *,
        enable_tools: list[str] | None = None,
        disable_tools: list[str] | None = None,
    ) -> None:
        """Create a core client around an initialized MCP session."""
        if not re.fullmatch(r"[a-zA-Z0-9_-]+", name):
            raise ValueError(
                f"MCPClient name '{name}' contains invalid characters; "
                "only letters, numbers, underscores, and hyphens are allowed.",
            )
        if not isinstance(session, ClientSession):
            raise TypeError("session must be an initialized ClientSession.")

        for label, names in (
            ("enable_tools", enable_tools),
            ("disable_tools", disable_tools),
        ):
            if names is not None and (
                not isinstance(names, list)
                or any(not isinstance(tool_name, str) for tool_name in names)
            ):
                raise ValueError(f"{label} must contain only strings.")

        if enable_tools is not None and disable_tools is not None:
            overlap = set(enable_tools).intersection(disable_tools)
            if overlap:
                raise ValueError(
                    "enable_tools and disable_tools must not overlap: "
                    f"{overlap}",
                )

        self.name = name
        self.session = session
        self.enable_tools = enable_tools
        self.disable_tools = disable_tools

    def _tool_is_enabled(self, name: str) -> bool:
        """Return whether a tool passes the configured filters."""
        if self.enable_tools is not None:
            return name in self.enable_tools
        if self.disable_tools is not None:
            return name not in self.disable_tools
        return True

    async def list_tools(self) -> list[mcp.types.Tool]:
        """List currently available MCP tools."""
        result = await self.session.list_tools()
        return [
            tool
            for tool in result.tools
            if self._tool_is_enabled(tool.name)
        ]

    async def get_tool(self, name: str) -> mcp.types.Tool:
        """Return the current descriptor for one enabled MCP tool."""
        for tool in await self.list_tools():
            if tool.name == name:
                return tool
        raise ValueError(
            f"Enabled tool '{name}' was not found on MCP server '{self.name}'.",
        )

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any] | None = None,
    ) -> mcp.types.CallToolResult:
        """Call an enabled MCP tool and return the SDK result unchanged."""
        if not self._tool_is_enabled(name):
            raise ValueError(
                f"Tool '{name}' is disabled for MCP server '{self.name}'.",
            )
        return await self.session.call_tool(name, arguments or {})