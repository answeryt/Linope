# -*- coding: utf-8 -*-
"""Request cancellation of a background agent's current turn."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any, Optional


PLUGIN_NAME = "interrupt_agent"
PLUGIN_VERSION = "1.0"

ControlFn = Callable[..., dict[str, Any]]

INTERRUPT_SCHEMA: dict[str, Any] = {
    "name": "interrupt_agent",
    "description": (
        "Request cancellation of a background agent's current turn by its agent "
        "id. Only the current turn stops. This call returns as soon as the stop "
        "request is accepted."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "agent_id": {
                "type": "string",
                "description": "The agent id of the running agent to interrupt.",
            },
        },
        "required": ["agent_id"],
    },
}


def tool_schemas() -> list[dict[str, Any]]:
    return [INTERRUPT_SCHEMA]



def load(kind, body, call_params=None):
    """Load one tool call. Argument shape stays in this plugin."""
    if kind != "tool":
        raise ValueError(f"这个进程不能装入 {kind}")
    if not isinstance(body, dict):
        raise TypeError("tool 的内容必须是映射")
    return dispatch('interrupt_agent', body, **(call_params or {}))


def dispatch(name: str, arguments: dict[str, Any], **kwargs: Any) -> str:
    if name != "interrupt_agent":
        return _error(f"unknown tool: {name}")
    agent_id = str(arguments.get("agent_id") or "").strip()
    if not agent_id:
        return _error("agent_id must be a non-empty string")
    control: Optional[ControlFn] = kwargs.get("control")
    if control is None:
        return _error("Host must inject a `control` callback.")
    result = control(action="interrupt_agent", agent_id=agent_id)
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

