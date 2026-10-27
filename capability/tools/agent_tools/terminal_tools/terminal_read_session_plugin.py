# -*- coding: utf-8 -*-
"""Read retained output from a persistent terminal without sending input."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any, Optional


PLUGIN_NAME = "terminal_read_session"
PLUGIN_VERSION = "1.0"

BackendFn = Callable[..., dict[str, Any]]

TERMINAL_READ_SCHEMA: dict[str, Any] = {
    "name": "terminal_read",
    "description": (
        "Read a bounded page of retained output from a persistent terminal "
        "without sending input."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "sessionId": {"type": "string", "description": "Terminal session id."},
            "offset": {
                "type": "number",
                "description": "Newest-relative line offset (default 0).",
            },
            "count": {
                "type": "number",
                "description": "Requested line count (default 500; backend caps apply).",
            },
        },
        "required": ["sessionId"],
    },
}


def tool_schemas() -> list[dict[str, Any]]:
    return [TERMINAL_READ_SCHEMA]



def load(kind, body, call_params=None):
    """Load one tool call. Argument shape stays in this plugin."""
    if kind != "tool":
        raise ValueError(f"This process cannot load {kind}")
    if not isinstance(body, dict):
        raise TypeError("tool content must be a mapping")
    return dispatch('terminal_read', body, **(call_params or {}))


def dispatch(name: str, arguments: dict[str, Any], **kwargs: Any) -> str:
    if name != "terminal_read":
        return _error(f"unknown tool: {name}")
    return terminal_read(
        str(arguments.get("sessionId") or ""),
        arguments.get("offset"),
        arguments.get("count"),
        **kwargs,
    )


def terminal_read(
    session_id: str,
    offset: Any = None,
    count: Any = None,
    backend: Optional[BackendFn] = None,
) -> str:
    if not session_id.strip():
        return _error("sessionId is required")
    if backend is None:
        return _error("Host must inject a persistent terminal `backend`.")
    result = backend(action="terminal_read", sessionId=session_id, offset=offset, count=count)
    return json.dumps({"success": True, **result}, ensure_ascii=False)


def _error(message: str, **details: Any) -> str:
    payload = {"success": False, "error": message}
    payload.update(details)
    return json.dumps(payload, ensure_ascii=False)

def capability_profile(capability_id, changes):
    """This process leases a tool and the shared project workspace."""
    from kernel.process.profiles import tool_with_workspace

    return tool_with_workspace(capability_id, changes)

