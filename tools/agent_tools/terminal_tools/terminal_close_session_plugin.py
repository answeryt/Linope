# -*- coding: utf-8 -*-
"""Close one persistent terminal and wait until its process tree is gone."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any, Optional


PLUGIN_NAME = "terminal_close_session"
PLUGIN_VERSION = "1.0"

BackendFn = Callable[..., dict[str, Any]]

TERMINAL_CLOSE_SCHEMA: dict[str, Any] = {
    "name": "terminal_close",
    "description": (
        "Close one persistent terminal and wait until its captured owned "
        "process tree is gone."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "sessionId": {"type": "string", "description": "Terminal session id."},
        },
        "required": ["sessionId"],
    },
}


def tool_schemas() -> list[dict[str, Any]]:
    return [TERMINAL_CLOSE_SCHEMA]


def dispatch(name: str, arguments: dict[str, Any], **kwargs: Any) -> str:
    if name != "terminal_close":
        return _error(f"unknown tool: {name}")
    return terminal_close(str(arguments.get("sessionId") or ""), **kwargs)


def terminal_close(session_id: str, backend: Optional[BackendFn] = None) -> str:
    if not session_id.strip():
        return _error("sessionId is required")
    if backend is None:
        return _error("Host must inject a persistent terminal `backend`.")
    result = backend(action="terminal_close", sessionId=session_id)
    return json.dumps({"success": True, **result}, ensure_ascii=False)


def _error(message: str, **details: Any) -> str:
    payload = {"success": False, "error": message}
    payload.update(details)
    return json.dumps(payload, ensure_ascii=False)
