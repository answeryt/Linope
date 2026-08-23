# -*- coding: utf-8 -*-
"""Search prior events in one authorized session."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any, Optional


PLUGIN_NAME = "session_event_search"
PLUGIN_VERSION = "1.0"

QueryFn = Callable[..., dict[str, Any]]

SESSION_EVENT_SEARCH_SCHEMA: dict[str, Any] = {
    "name": "session_event_search",
    "description": (
        "Search prior events in one authorized session; the current session "
        "excludes the step performing this call."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "session_id": {"type": "string"},
            "query": {"type": "string", "description": "Literal full-text query."},
            "seq_from": {"type": "integer"},
            "seq_to": {"type": "integer"},
            "time_from": {"type": "string"},
            "time_to": {"type": "string"},
            "event_types": {"type": "array", "items": {"type": "string"}},
            "surfaces": {
                "type": "array",
                "items": {"type": "string", "enum": ["current", "shadowed", "log-only"]},
            },
        },
        "required": ["query"],
    },
}


def tool_schemas() -> list[dict[str, Any]]:
    return [SESSION_EVENT_SEARCH_SCHEMA]


def dispatch(name: str, arguments: dict[str, Any], **kwargs: Any) -> str:
    if name != "session_event_search":
        return _error(f"unknown tool: {name}")
    if not str(arguments.get("query") or "").strip():
        return _error("query must be a non-empty string")
    query = kwargs.get("query")
    if query is None:
        return _error("Host must inject a session `query` engine.")
    result = query(name="session_event_search", arguments=arguments)
    return json.dumps({"success": True, **result}, ensure_ascii=False)


def _error(message: str, **details: Any) -> str:
    payload = {"success": False, "error": message}
    payload.update(details)
    return json.dumps(payload, ensure_ascii=False)
