# -*- coding: utf-8 -*-
"""Read one unabridged session event and optional neighbors."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any, Optional


PLUGIN_NAME = "session_event_read"
PLUGIN_VERSION = "1.0"

QueryFn = Callable[..., dict[str, Any]]

SESSION_EVENT_READ_SCHEMA: dict[str, Any] = {
    "name": "session_event_read",
    "description": (
        "Read one full unabridged event and optional neighboring raw-event "
        "summaries from an authorized session."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "session_id": {
                "type": "string",
                "description": "Target session id. Omit for the current session.",
            },
            "seq": {"type": "integer", "description": "Target event sequence number."},
            "before": {
                "type": "integer",
                "description": "Number of preceding raw events to summarize.",
            },
            "after": {
                "type": "integer",
                "description": "Number of following raw events to summarize.",
            },
        },
        "required": ["seq"],
    },
}


def tool_schemas() -> list[dict[str, Any]]:
    return [SESSION_EVENT_READ_SCHEMA]



def load(kind, body, call_params=None):
    """Load one tool call. Argument shape stays in this plugin."""
    if kind != "tool":
        raise ValueError(f"这个进程不能装入 {kind}")
    if not isinstance(body, dict):
        raise TypeError("tool 的内容必须是映射")
    return dispatch('session_event_read', body, **(call_params or {}))


def dispatch(name: str, arguments: dict[str, Any], **kwargs: Any) -> str:
    if name != "session_event_read":
        return _error(f"unknown tool: {name}")
    if arguments.get("seq") is None:
        return _error("seq is required")
    return _forward(arguments, **kwargs)


def _forward(arguments: dict[str, Any], query: Optional[QueryFn] = None) -> str:
    if query is None:
        return _error("Host must inject a session `query` engine.")
    result = query(name="session_event_read", arguments=arguments)
    return json.dumps({"success": True, **result}, ensure_ascii=False)


def _error(message: str, **details: Any) -> str:
    payload = {"success": False, "error": message}
    payload.update(details)
    return json.dumps(payload, ensure_ascii=False)

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

