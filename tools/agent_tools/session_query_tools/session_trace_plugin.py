# -*- coding: utf-8 -*-
"""Read authorized session lineage around one session."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any


PLUGIN_NAME = "session_trace"
PLUGIN_VERSION = "1.0"

QueryFn = Callable[..., dict[str, Any]]

SESSION_TRACE_SCHEMA: dict[str, Any] = {
    "name": "session_trace",
    "description": (
        "Read the authorized session lineage around one session, including "
        "complete visible ancestor and descendant relationships."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "session_id": {
                "type": "string",
                "description": "Target session id. Omit for the current session.",
            },
        },
    },
}


def tool_schemas() -> list[dict[str, Any]]:
    return [SESSION_TRACE_SCHEMA]


def dispatch(name: str, arguments: dict[str, Any], **kwargs: Any) -> str:
    if name != "session_trace":
        return _error(f"unknown tool: {name}")
    query = kwargs.get("query")
    if query is None:
        return _error("Host must inject a session `query` engine.")
    result = query(name="session_trace", arguments=arguments)
    return json.dumps({"success": True, **result}, ensure_ascii=False)


def _error(message: str, **details: Any) -> str:
    payload = {"success": False, "error": message}
    payload.update(details)
    return json.dumps(payload, ensure_ascii=False)
