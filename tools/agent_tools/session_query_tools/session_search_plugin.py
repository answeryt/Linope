# -*- coding: utf-8 -*-
"""Search prior sessions and return the strongest matching event from each."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any


PLUGIN_NAME = "session_search"
PLUGIN_VERSION = "1.0"

QueryFn = Callable[..., dict[str, Any]]

SESSION_SEARCH_SCHEMA: dict[str, Any] = {
    "name": "session_search",
    "description": (
        "Search prior sessions in the caller workspace and return the strongest "
        "matching event from each session."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Literal full-text query."},
            "session_ids": {"type": "array", "items": {"type": "string"}},
            "created_at_from": {"type": "string"},
            "created_at_to": {"type": "string"},
            "parent_session_ids": {"type": "array", "items": {"type": "string"}},
            "include_root_sessions": {"type": "boolean"},
            "availability": {
                "type": "array",
                "items": {"type": "string", "enum": ["live", "persisted"]},
            },
            "event_seq_from": {"type": "integer"},
            "event_seq_to": {"type": "integer"},
            "event_time_from": {"type": "string"},
            "event_time_to": {"type": "string"},
            "event_types": {"type": "array", "items": {"type": "string"}},
            "event_surfaces": {
                "type": "array",
                "items": {"type": "string", "enum": ["current", "shadowed", "log-only"]},
            },
        },
        "required": ["query"],
    },
}


def tool_schemas() -> list[dict[str, Any]]:
    return [SESSION_SEARCH_SCHEMA]


def dispatch(name: str, arguments: dict[str, Any], **kwargs: Any) -> str:
    if name != "session_search":
        return _error(f"unknown tool: {name}")
    if not str(arguments.get("query") or "").strip():
        return _error("query must be a non-empty string")
    query = kwargs.get("query")
    if query is None:
        return _error("Host must inject a session `query` engine.")
    result = query(name="session_search", arguments=arguments)
    return json.dumps({"success": True, **result}, ensure_ascii=False)


def _error(message: str, **details: Any) -> str:
    payload = {"success": False, "error": message}
    payload.update(details)
    return json.dumps(payload, ensure_ascii=False)
