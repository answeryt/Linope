"""Build one tool request for a process that already exists, or name the one to start."""

from __future__ import annotations

import importlib.util
from typing import Any

from kernel.process.process_creat.instances import describe_instance


def tool_capability(name: str) -> str:
    value = str(name).strip()
    if value.startswith("agent:"):
        return value
    return value if value.startswith("tools.") else f"tools.{value}"


def tool_request(name: str, arguments: Any, *, call_id: str = "", task_id: str = "") -> dict[str, Any]:
    """The process message for one tool step. The call id stays on the envelope."""
    body = arguments if isinstance(arguments, dict) else {}
    return {
        "operation": "load",
        "kind": "tool",
        "body": body,
        "tool_name": str(name),
        "call_id": call_id,
        "task_id": task_id,
    }


def declared_tool_schema(capability: str) -> list[dict[str, Any]]:
    """Read ``tool_schemas`` from the capability's own plugin. Do not call the tool."""
    try:
        definition = describe_instance(capability)
    except KeyError:
        return []
    found: list[dict[str, Any]] = []
    for raw in definition.module_paths:
        spec = importlib.util.spec_from_file_location(f"linope_schema_{capability}", raw)
        if spec is None or spec.loader is None:
            continue
        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)
        except Exception:
            continue
        reader = getattr(module, "tool_schemas", None)
        if not callable(reader):
            continue
        schemas = reader()
        if isinstance(schemas, list):
            found.extend(item for item in schemas if isinstance(item, dict))
    return found
