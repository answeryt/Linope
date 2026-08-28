# -*- coding: utf-8 -*-
"""Standalone MCP protocol discovery and resource plugin.

The plugin imports no project sibling.  Supply an initialized MCP
``ClientSession`` and, when available, its ``InitializeResult``.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Awaitable, Callable


PLUGIN_NAME = "mcp_protocol_resources"
PLUGIN_VERSION = "1.0"


class MCPUnsupportedCapability(RuntimeError):
    """Raised when a server explicitly omits an MCP request family."""


class MCPPaginationError(RuntimeError):
    """Raised when a server returns an invalid or cycling cursor."""


@dataclass(frozen=True)
class ProtocolSnapshot:
    """One capability-aware snapshot of a server's discoverable objects."""

    tools: tuple[Any, ...] = ()
    resources: tuple[Any, ...] = ()
    prompts: tuple[Any, ...] = ()


class MCPProtocolPlugin:
    """Expose paginated tools, resources, and prompts on one MCP session."""

    def __init__(
        self,
        session: Any,
        *,
        initialize_result: Any = None,
        max_pages: int = 50,
        request_timeout: float = 60.0,
        serialize_requests: bool = True,
    ) -> None:
        if session is None:
            raise TypeError("session is required.")
        if max_pages < 1:
            raise ValueError("max_pages must be at least 1.")
        if request_timeout <= 0:
            raise ValueError("request_timeout must be positive.")
        self.session = session
        self.initialize_result = initialize_result
        self.max_pages = max_pages
        self.request_timeout = request_timeout
        self._rpc_lock = asyncio.Lock() if serialize_requests else None

    def advertises(self, capability: str) -> bool:
        """Return whether initialization advertises a request family.

        Missing initialization metadata uses a permissive legacy fallback.
        """
        result = self.initialize_result
        capabilities = (
            getattr(result, "capabilities", None) if result is not None else None
        )
        if capabilities is None:
            return True
        if isinstance(capabilities, dict):
            return capabilities.get(capability) is not None
        return getattr(capabilities, capability, None) is not None

    def _require(self, capability: str, method_name: str) -> Callable[..., Awaitable[Any]]:
        if not self.advertises(capability):
            raise MCPUnsupportedCapability(
                f"MCP server does not advertise the '{capability}' capability.",
            )
        method = getattr(self.session, method_name, None)
        if not callable(method):
            raise MCPUnsupportedCapability(
                f"MCP session does not implement {method_name}().",
            )
        return method

    async def _invoke(self, operation: Callable[[], Awaitable[Any]]) -> Any:
        async def run() -> Any:
            return await asyncio.wait_for(
                operation(),
                timeout=self.request_timeout,
            )

        if self._rpc_lock is None:
            return await run()
        async with self._rpc_lock:
            return await run()

    async def _paginate(
        self,
        method: Callable[..., Awaitable[Any]],
        items_attr: str,
    ) -> list[Any]:
        async def drain() -> list[Any]:
            items: list[Any] = []
            cursor: str | None = None
            seen_cursors: set[str] = set()

            for _ in range(self.max_pages):
                page = await asyncio.wait_for(
                    method(cursor=cursor) if cursor else method(),
                    timeout=self.request_timeout,
                )
                page_items = getattr(page, items_attr, None)
                if page_items is None and isinstance(page, dict):
                    page_items = page.get(items_attr)
                items.extend(page_items or [])

                next_cursor = getattr(page, "nextCursor", None)
                if next_cursor is None and isinstance(page, dict):
                    next_cursor = page.get("nextCursor")
                if not isinstance(next_cursor, str) or not next_cursor:
                    return items
                if next_cursor in seen_cursors:
                    raise MCPPaginationError(
                        f"MCP {items_attr} pagination repeated cursor "
                        f"{next_cursor!r}.",
                    )
                seen_cursors.add(next_cursor)
                cursor = next_cursor

            raise MCPPaginationError(
                f"MCP {items_attr} pagination exceeded {self.max_pages} pages.",
            )

        if self._rpc_lock is None:
            return await drain()
        async with self._rpc_lock:
            return await drain()

    async def list_tools(self) -> list[Any]:
        """Return all advertised tools across every cursor page."""
        method = self._require("tools", "list_tools")
        return await self._paginate(method, "tools")

    async def list_resources(self) -> list[Any]:
        """Return all advertised resources across every cursor page."""
        method = self._require("resources", "list_resources")
        return await self._paginate(method, "resources")

    async def read_resource(self, uri: str) -> Any:
        """Read one resource by URI and return the SDK result unchanged."""
        if not isinstance(uri, str) or not uri.strip():
            raise ValueError("uri must be a non-empty string.")
        method = self._require("resources", "read_resource")
        return await self._invoke(lambda: method(uri))

    async def list_prompts(self) -> list[Any]:
        """Return all advertised prompts across every cursor page."""
        method = self._require("prompts", "list_prompts")
        return await self._paginate(method, "prompts")

    async def get_prompt(
        self,
        name: str,
        arguments: dict[str, Any] | None = None,
    ) -> Any:
        """Resolve one prompt and return the SDK result unchanged."""
        if not isinstance(name, str) or not name.strip():
            raise ValueError("name must be a non-empty string.")
        method = self._require("prompts", "get_prompt")
        return await self._invoke(
            lambda: method(name, arguments=arguments or {}),
        )

    async def snapshot(self) -> ProtocolSnapshot:
        """Discover every request family the server advertises."""
        tools: list[Any] = []
        resources: list[Any] = []
        prompts: list[Any] = []
        if self.advertises("tools"):
            tools = await self.list_tools()
        if self.advertises("resources"):
            resources = await self.list_resources()
        if self.advertises("prompts"):
            prompts = await self.list_prompts()
        return ProtocolSnapshot(
            tools=tuple(tools),
            resources=tuple(resources),
            prompts=tuple(prompts),
        )

    @staticmethod
    def resource_to_dict(resource: Any) -> dict[str, Any]:
        """Convert an MCP resource descriptor to host-neutral data."""
        output: dict[str, Any] = {}
        for source, target in (
            ("uri", "uri"),
            ("name", "name"),
            ("description", "description"),
            ("mimeType", "mimeType"),
        ):
            value = getattr(resource, source, None)
            if value is not None:
                output[target] = str(value) if source == "uri" else value
        return output

    @staticmethod
    def prompt_to_dict(prompt: Any) -> dict[str, Any]:
        """Convert an MCP prompt descriptor to host-neutral data."""
        output: dict[str, Any] = {"name": getattr(prompt, "name", "")}
        description = getattr(prompt, "description", None)
        if description:
            output["description"] = description
        arguments = []
        for argument in getattr(prompt, "arguments", None) or []:
            entry = {"name": getattr(argument, "name", "")}
            for key in ("description", "required"):
                value = getattr(argument, key, None)
                if value is not None:
                    entry[key] = value
            arguments.append(entry)
        if arguments:
            output["arguments"] = arguments
        return output
