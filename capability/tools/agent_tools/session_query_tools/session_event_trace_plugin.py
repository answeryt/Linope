# -*- coding: utf-8 -*-
"""Read replacements and relationships for one session event."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any, Optional


PLUGIN_NAME = "session_event_trace"
PLUGIN_VERSION = "1.0"

QueryFn = Callable[..., dict[str, Any]]

SESSION_EVENT_TRACE_SCHEMA: dict[str, Any] = {
    "name": "session_event_trace",
    "description": (
        "Read every direct replacement and relationship to a cited source event "
        "for one event in an authorized session."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "session_id": {"type": "string"},
            "seq": {"type": "integer", "description": "Target event sequence number."},
        },
        "required": ["seq"],
    },
}


def tool_schemas() -> list[dict[str, Any]]:
    return [SESSION_EVENT_TRACE_SCHEMA]



def load(kind, body, call_params=None):
    """Load one tool call. Argument shape stays in this plugin."""
    if kind != "tool":
        raise ValueError(f"这个进程不能装入 {kind}")
    if not isinstance(body, dict):
        raise TypeError("tool 的内容必须是映射")
    return dispatch('session_event_trace', body, **(call_params or {}))


def dispatch(name: str, arguments: dict[str, Any], **kwargs: Any) -> str:
    if name != "session_event_trace":
        return _error(f"unknown tool: {name}")
    if arguments.get("seq") is None:
        return _error("seq is required")
    query = kwargs.get("query")
    if query is None:
        return _error("Host must inject a session `query` engine.")
    result = query(name="session_event_trace", arguments=arguments)
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

