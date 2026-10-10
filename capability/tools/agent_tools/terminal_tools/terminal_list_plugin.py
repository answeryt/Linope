# -*- coding: utf-8 -*-
"""List persistent terminal sessions owned by the current agent."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any, Optional


PLUGIN_NAME = "terminal_list"
PLUGIN_VERSION = "1.0"

BackendFn = Callable[..., dict[str, Any]]

TERMINAL_LIST_SCHEMA: dict[str, Any] = {
    "name": "terminal_list",
    "description": "List persistent terminal sessions owned by the current agent.",
    "parameters": {"type": "object", "properties": {}},
}


def tool_schemas() -> list[dict[str, Any]]:
    return [TERMINAL_LIST_SCHEMA]



def load(kind, body, call_params=None):
    """Load one tool call. Argument shape stays in this plugin."""
    if kind != "tool":
        raise ValueError(f"这个进程不能装入 {kind}")
    if not isinstance(body, dict):
        raise TypeError("tool 的内容必须是映射")
    return dispatch('terminal_list', body, **(call_params or {}))


def dispatch(name: str, arguments: dict[str, Any], **kwargs: Any) -> str:
    if name != "terminal_list":
        return _error(f"unknown tool: {name}")
    return terminal_list(**kwargs)


def terminal_list(backend: Optional[BackendFn] = None) -> str:
    if backend is None:
        return _error("Host must inject a persistent terminal `backend`.")
    result = backend(action="terminal_list")
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

