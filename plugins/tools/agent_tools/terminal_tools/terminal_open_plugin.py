# -*- coding: utf-8 -*-
"""Create a persistent, owner-isolated terminal session."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any, Optional


PLUGIN_NAME = "terminal_open"
PLUGIN_VERSION = "1.0"

BackendFn = Callable[..., dict[str, Any]]

TERMINAL_OPEN_SCHEMA: dict[str, Any] = {
    "name": "terminal_open",
    "description": (
        "Create a persistent, owner-isolated terminal session from a registered "
        "backend type. Use this for shell or REPL state that must survive across "
        "tool calls."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "type": {
                "type": "string",
                "description": 'Registered terminal backend type, usually "shell".',
            },
            "name": {
                "type": "string",
                "description": 'Optional owner-local display name such as "main" or "gdb".',
            },
            "cwd": {
                "type": "string",
                "description": "Initial working directory. Defaults to the deployment workspace root.",
            },
        },
        "required": ["type"],
    },
}


def tool_schemas() -> list[dict[str, Any]]:
    return [TERMINAL_OPEN_SCHEMA]


def dispatch(name: str, arguments: dict[str, Any], **kwargs: Any) -> str:
    if name != "terminal_open":
        return _error(f"unknown tool: {name}")
    return terminal_open(
        str(arguments.get("type") or ""),
        arguments.get("name"),
        arguments.get("cwd"),
        **kwargs,
    )


def terminal_open(
    session_type: str,
    name: Optional[str] = None,
    cwd: Optional[str] = None,
    backend: Optional[BackendFn] = None,
) -> str:
    if not session_type.strip():
        return _error("type is required")
    if backend is None:
        return _error("Host must inject a persistent terminal `backend`.")
    result = backend(action="terminal_open", type=session_type, name=name, cwd=cwd)
    return json.dumps({"success": True, **result}, ensure_ascii=False)


def _error(message: str, **details: Any) -> str:
    payload = {"success": False, "error": message}
    payload.update(details)
    return json.dumps(payload, ensure_ascii=False)
