# -*- coding: utf-8 -*-
"""Standalone MCP tool normalization and registry plugin.

The plugin owns no transport and imports no project sibling.  A host may use
its in-memory registry directly or mirror change events into another registry.
"""

from __future__ import annotations

import asyncio
import copy
import hashlib
import inspect
import re
from dataclasses import dataclass
from typing import Any, Callable, Iterable


PLUGIN_NAME = "mcp_tool_manager"
PLUGIN_VERSION = "1.0"
MCP_TOOL_PREFIX = "mcp__"


def sanitize_name(value: str) -> str:
    """Return a provider-safe MCP tool-name component."""
    return re.sub(r"[^A-Za-z0-9_]", "_", str(value or ""))


def prefixed_tool_name(server_name: str, tool_name: str) -> str:
    """Build ``mcp__<server>__<tool>`` without an ambiguous boundary."""
    qualified = (
        f"{MCP_TOOL_PREFIX}{sanitize_name(server_name)}__{sanitize_name(tool_name)}"
    )
    if len(qualified) <= 64:
        return qualified
    digest = hashlib.sha256(
        f"{server_name}\0{tool_name}".encode("utf-8"),
    ).hexdigest()[:8]
    return f"{qualified[:55]}_{digest}"


def _collision_safe_name(
    candidate: str,
    server_name: str,
    remote_name: str,
    occupied: set[str],
) -> str:
    if candidate not in occupied:
        return candidate
    digest = hashlib.sha256(
        f"{server_name}\0{remote_name}".encode("utf-8"),
    ).hexdigest()[:8]
    stem = candidate[:55]
    resolved = f"{stem}_{digest}"
    counter = 2
    while resolved in occupied:
        suffix = f"_{digest}_{counter}"
        resolved = f"{candidate[:64 - len(suffix)]}{suffix}"
        counter += 1
    return resolved


def normalize_input_schema(schema: dict[str, Any] | None) -> dict[str, Any]:
    """Repair common MCP JSON Schema incompatibilities for LLM providers."""
    if not isinstance(schema, dict) or not schema:
        return {"type": "object", "properties": {}}

    def rewrite(node: Any, *, property_map: bool = False) -> Any:
        if isinstance(node, list):
            return [rewrite(item) for item in node]
        if not isinstance(node, dict):
            return node

        output: dict[str, Any] = {}
        for key, value in node.items():
            output_key = key if property_map else ("$defs" if key == "definitions" else key)
            if key in {"properties", "patternProperties"} and isinstance(value, dict):
                output[output_key] = {
                    prop_name: rewrite(prop_schema)
                    for prop_name, prop_schema in value.items()
                }
            else:
                output[output_key] = rewrite(value)

        ref = output.get("$ref")
        if isinstance(ref, str) and ref.startswith("#/definitions/"):
            output["$ref"] = "#/$defs/" + ref[len("#/definitions/"):]

        any_of = output.get("anyOf")
        if isinstance(any_of, list):
            non_null = [
                item
                for item in any_of
                if not (isinstance(item, dict) and item.get("type") == "null")
            ]
            if len(non_null) == 1 and len(non_null) != len(any_of):
                nullable = rewrite(non_null[0])
                if isinstance(nullable, dict):
                    siblings = {
                        key: value
                        for key, value in output.items()
                        if key not in {"anyOf", "default"}
                    }
                    output = {**nullable, **siblings, "nullable": True}

        node_type = output.get("type")
        if isinstance(node_type, list) and "null" in node_type:
            non_null_types = [item for item in node_type if item != "null"]
            if len(non_null_types) == 1:
                output["type"] = non_null_types[0]
                output["nullable"] = True

        if not output.get("type") and (
            "properties" in output or "required" in output
        ):
            output["type"] = "object"
        if output.get("type") == "object":
            properties = output.get("properties")
            if not isinstance(properties, dict):
                properties = {}
                output["properties"] = properties
            required = output.get("required")
            if isinstance(required, list):
                valid = [
                    name
                    for name in required
                    if isinstance(name, str) and name in properties
                ]
                if valid:
                    output["required"] = valid
                else:
                    output.pop("required", None)
        return output

    normalized = rewrite(copy.deepcopy(schema))
    if not isinstance(normalized, dict):
        return {"type": "object", "properties": {}}
    if normalized.get("type") == "object":
        normalized.setdefault("properties", {})
    return normalized


@dataclass(frozen=True)
class ToolRecord:
    """Host-neutral registered MCP tool."""

    name: str
    server_name: str
    remote_name: str
    schema: dict[str, Any]
    handler: Callable[..., Any] | None = None
    utility: bool = False


class MCPToolManagerPlugin:
    """Normalize, filter, register, and atomically refresh MCP tools."""

    def __init__(
        self,
        *,
        on_change: Callable[[dict[str, Any]], Any] | None = None,
    ) -> None:
        self.on_change = on_change
        self._records: dict[str, ToolRecord] = {}
        self._server_names: dict[str, set[str]] = {}
        self._generation = 0
        self._refresh_lock = asyncio.Lock()

    @property
    def generation(self) -> int:
        return self._generation

    def records(self, server_name: str | None = None) -> tuple[ToolRecord, ...]:
        """Return an immutable registry snapshot."""
        if server_name is None:
            return tuple(self._records.values())
        names = self._server_names.get(server_name, set())
        return tuple(self._records[name] for name in names if name in self._records)

    def resolve(self, registered_name: str) -> ToolRecord:
        """Resolve a registered tool or raise a useful lookup error."""
        try:
            return self._records[registered_name]
        except KeyError as error:
            raise KeyError(f"MCP tool {registered_name!r} is not registered.") from error

    @staticmethod
    def convert_tool(server_name: str, tool: Any) -> dict[str, Any]:
        """Convert one SDK Tool descriptor to a host-neutral function schema."""
        remote_name = str(getattr(tool, "name", "") or "")
        if not remote_name:
            raise ValueError("MCP tool descriptor has no name.")
        return {
            "name": prefixed_tool_name(server_name, remote_name),
            "description": (
                getattr(tool, "description", None)
                or f"MCP tool {remote_name} from {server_name}"
            ),
            "parameters": normalize_input_schema(
                getattr(tool, "inputSchema", None),
            ),
        }

    @staticmethod
    def _name_filter(
        tools: Iterable[Any],
        include: Iterable[str] | None,
        exclude: Iterable[str] | None,
    ) -> list[Any]:
        include_names = {str(name) for name in include or ()}
        exclude_names = {str(name) for name in exclude or ()}
        selected = []
        for tool in tools:
            name = str(getattr(tool, "name", "") or "")
            if include_names and name not in include_names:
                continue
            if not include_names and name in exclude_names:
                continue
            selected.append(tool)
        return selected

    def register_server_tools(
        self,
        server_name: str,
        tools: Iterable[Any],
        *,
        handler_factory: Callable[[str], Callable[..., Any]] | None = None,
        include: Iterable[str] | None = None,
        exclude: Iterable[str] | None = None,
        reserved_names: Iterable[str] = (),
    ) -> tuple[ToolRecord, ...]:
        """Replace one server's records atomically with collision protection."""
        if not server_name:
            raise ValueError("server_name is required.")
        reserved = set(reserved_names)
        staged: dict[str, ToolRecord] = {}
        for tool in self._name_filter(tools, include, exclude):
            schema = self.convert_tool(server_name, tool)
            remote_name = str(getattr(tool, "name"))
            occupied = reserved | set(staged)
            occupied.update(
                name
                for name, record in self._records.items()
                if record.server_name != server_name
            )
            name = _collision_safe_name(
                schema["name"],
                server_name,
                remote_name,
                occupied,
            )
            schema["name"] = name
            staged[name] = ToolRecord(
                name=name,
                server_name=server_name,
                remote_name=remote_name,
                schema=schema,
                handler=handler_factory(remote_name) if handler_factory else None,
            )

        old_names = set(self._server_names.get(server_name, set()))
        new_names = set(staged)
        for stale in old_names - new_names:
            self._records.pop(stale, None)
        self._records.update(staged)
        self._server_names[server_name] = new_names
        self._generation += 1
        self._notify(
            {
                "server": server_name,
                "generation": self._generation,
                "added": sorted(new_names - old_names),
                "removed": sorted(old_names - new_names),
            },
        )
        return tuple(staged.values())

    async def refresh_server_tools(
        self,
        server_name: str,
        list_tools: Callable[[], Any],
        **register_options: Any,
    ) -> tuple[ToolRecord, ...]:
        """Serialize list-changed refreshes and atomically publish results."""
        async with self._refresh_lock:
            tools = list_tools()
            if inspect.isawaitable(tools):
                tools = await tools
            if hasattr(tools, "tools"):
                tools = tools.tools
            return self.register_server_tools(
                server_name,
                tools or (),
                **register_options,
            )

    def deregister_server(self, server_name: str) -> tuple[str, ...]:
        """Remove every tool belonging to one server."""
        names = self._server_names.pop(server_name, set())
        for name in names:
            self._records.pop(name, None)
        if names:
            self._generation += 1
            self._notify(
                {
                    "server": server_name,
                    "generation": self._generation,
                    "added": [],
                    "removed": sorted(names),
                },
            )
        return tuple(sorted(names))

    def is_parallel_safe(
        self,
        tool_name: str,
        parallel_servers: Iterable[str],
    ) -> bool:
        """Check exact provenance instead of parsing an ambiguous tool name."""
        record = self._records.get(tool_name)
        return bool(record and record.server_name in set(parallel_servers))

    @staticmethod
    def utility_schemas(
        server_name: str,
        *,
        resources: bool,
        prompts: bool,
    ) -> list[dict[str, Any]]:
        """Build capability-gated resource and prompt utility schemas."""
        schemas: list[dict[str, Any]] = []
        if resources:
            schemas.extend(
                [
                    {
                        "name": prefixed_tool_name(server_name, "list_resources"),
                        "description": f"List resources from MCP server {server_name!r}",
                        "parameters": {"type": "object", "properties": {}},
                    },
                    {
                        "name": prefixed_tool_name(server_name, "read_resource"),
                        "description": f"Read a resource from MCP server {server_name!r}",
                        "parameters": {
                            "type": "object",
                            "properties": {"uri": {"type": "string"}},
                            "required": ["uri"],
                        },
                    },
                ],
            )
        if prompts:
            schemas.extend(
                [
                    {
                        "name": prefixed_tool_name(server_name, "list_prompts"),
                        "description": f"List prompts from MCP server {server_name!r}",
                        "parameters": {"type": "object", "properties": {}},
                    },
                    {
                        "name": prefixed_tool_name(server_name, "get_prompt"),
                        "description": f"Get a prompt from MCP server {server_name!r}",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "arguments": {
                                    "type": "object",
                                    "properties": {},
                                    "additionalProperties": True,
                                },
                            },
                            "required": ["name"],
                        },
                    },
                ],
            )
        return schemas

    def _notify(self, event: dict[str, Any]) -> None:
        if self.on_change is None:
            return
        result = self.on_change(event)
        if inspect.isawaitable(result):
            try:
                asyncio.get_running_loop().create_task(result)
            except RuntimeError:
                if inspect.iscoroutine(result):
                    result.close()

_MANAGER: MCPToolManagerPlugin | None = None


def manager() -> MCPToolManagerPlugin:
    """The one registry this process keeps. Hosts register servers into it."""
    global _MANAGER
    if _MANAGER is None:
        _MANAGER = MCPToolManagerPlugin()
    return _MANAGER


def load(kind, body, call_params=None):
    """Load one tool call. The body names a registered ``mcp__<server>__<tool>``.

    ``{"name": "list"}`` or an empty name returns the registered schemas. A
    handler receives the ``arguments`` mapping as its single argument.
    """
    del call_params
    name, arguments = _tool_call(kind, body)
    if not name or name == "list":
        return {"tools": [record.schema for record in manager().records()]}
    record = manager().resolve(name)
    if record.handler is None:
        raise LookupError(f"MCP tool {name!r} has no handler bound.")
    result = record.handler(arguments)
    if inspect.isawaitable(result):
        return asyncio.run(result)
    return result


async def load_async(kind, body, call_params=None):
    """Same as ``load`` but awaited on the process event loop."""
    del call_params
    name, arguments = _tool_call(kind, body)
    if not name or name == "list":
        return {"tools": [record.schema for record in manager().records()]}
    record = manager().resolve(name)
    if record.handler is None:
        raise LookupError(f"MCP tool {name!r} has no handler bound.")
    result = record.handler(arguments)
    return await result if inspect.isawaitable(result) else result


def _tool_call(kind, body) -> tuple[str, dict[str, Any]]:
    if kind != "tool":
        raise ValueError(f"这个进程不能装入 {kind}")
    if isinstance(body, str):
        body = {"name": body}
    if body is None:
        body = {}
    if not isinstance(body, dict):
        raise TypeError("tool 的内容必须是映射")
    arguments = body.get("arguments") or {}
    if not isinstance(arguments, dict):
        raise TypeError("arguments 必须是映射")
    return str(body.get("name") or ""), dict(arguments)


def capability_profile(capability_id, changes):
    """Tell the process this tool needs a tool resource."""
    from kernel.process.declaration import ProcessDeclaration, ResourceClaim
    from kernel.resource.definition import ResourceKind

    return ProcessDeclaration(
        capability=capability_id,
        resources=(
            ResourceClaim(kind=ResourceKind.TOOL, identity={"id": capability_id}),
        ),
    )

