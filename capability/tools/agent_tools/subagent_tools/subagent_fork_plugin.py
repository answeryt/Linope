# -*- coding: utf-8 -*-
"""One-shot forked subagent that inherits the parent conversation prefix."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any, Optional


PLUGIN_NAME = "subagent_fork"
PLUGIN_VERSION = "1.0"

SpawnFn = Callable[..., dict[str, Any]]

SUBAGENT_FORK_SCHEMA: dict[str, Any] = {
    "name": "subagent_fork",
    "description": (
        "Delegate a one-shot forked subagent that inherits this conversation's "
        "prefix. The call waits in the foreground by default. Set "
        "`run_in_background: true` to return a job id."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "description": {
                "type": "string",
                "description": "A short (3-5 word) description of the delegated task.",
            },
            "prompt": {
                "type": "string",
                "description": "The complete, self-contained task for the forked subagent.",
            },
            "run_in_background": {
                "type": "boolean",
                "description": "Whether to run as a background job and return its id.",
            },
        },
        "required": ["description", "prompt"],
    },
}


def tool_schemas() -> list[dict[str, Any]]:
    return [SUBAGENT_FORK_SCHEMA]



def load(kind, body, call_params=None):
    """Load one tool call. Argument shape stays in this plugin."""
    if kind != "tool":
        raise ValueError(f"这个进程不能装入 {kind}")
    if not isinstance(body, dict):
        raise TypeError("tool 的内容必须是映射")
    return dispatch('subagent_fork', body, **(call_params or {}))


def dispatch(name: str, arguments: dict[str, Any], **kwargs: Any) -> str:
    if name != "subagent_fork":
        return _error(f"unknown tool: {name}")
    description = str(arguments.get("description") or "").strip()
    prompt = str(arguments.get("prompt") or "")
    if not description or not prompt.strip():
        return _error("description and prompt are required")
    spawn: Optional[SpawnFn] = kwargs.get("spawn")
    if spawn is None:
        return _error("Host must inject a `spawn` callback.")
    result = spawn(
        tool_name="subagent_fork",
        description=description,
        prompt=prompt,
        run_in_background=bool(arguments.get("run_in_background")),
    )
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

