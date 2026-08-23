# -*- coding: utf-8 -*-
"""List continuable background subagents by durable id and label."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any, Optional


PLUGIN_NAME = "list_agents"
PLUGIN_VERSION = "1.0"

ControlFn = Callable[..., dict[str, Any]]

LIST_AGENTS_SCHEMA: dict[str, Any] = {
    "name": "list_agents",
    "description": (
        "List your continuable background subagents by durable id and label. "
        "Status comes from the live registry: running, idle, or ready. Scope "
        "`descendants` walks the whole tree below you."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "scope": {
                "type": "string",
                "enum": ["children", "descendants"],
                "description": "children (default) or descendants.",
            },
        },
    },
}


def tool_schemas() -> list[dict[str, Any]]:
    return [LIST_AGENTS_SCHEMA]


def dispatch(name: str, arguments: dict[str, Any], **kwargs: Any) -> str:
    if name != "list_agents":
        return _error(f"unknown tool: {name}")
    scope = str(arguments.get("scope") or "children")
    if scope not in {"children", "descendants"}:
        return _error("scope must be children or descendants")
    control: Optional[ControlFn] = kwargs.get("control")
    if control is None:
        return _error("Host must inject a `control` callback.")
    result = control(action="list_agents", scope=scope)
    return json.dumps({"success": True, **result}, ensure_ascii=False)


def _error(message: str, **details: Any) -> str:
    payload = {"success": False, "error": message}
    payload.update(details)
    return json.dumps(payload, ensure_ascii=False)
