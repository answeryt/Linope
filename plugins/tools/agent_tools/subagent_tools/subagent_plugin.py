# -*- coding: utf-8 -*-
"""Delegate a self-contained task to a Host-injected subagent backend."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any, Optional


PLUGIN_NAME = "subagent"
PLUGIN_VERSION = "1.0"

SpawnFn = Callable[..., dict[str, Any]]

SUBAGENT_SCHEMA: dict[str, Any] = {
    "name": "subagent",
    "description": (
        "Delegate a self-contained task to a subagent (a separate agent that "
        "works in its own context) to offload focused, independent work — "
        "research, a scoped implementation, an analysis — so it does not consume "
        "this conversation's context. The subagent returns its result, not its "
        "intermediate steps. Give it a complete, standalone prompt: it does not "
        "see this conversation. This call waits for the result by default. Set "
        "`run_in_background: true` to return a job id; collect with `job_output` "
        "and stop with `job_kill`."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "description": {
                "type": "string",
                "description": "A short (3-5 word) description of the delegated task, for display.",
            },
            "prompt": {
                "type": "string",
                "description": (
                    "The complete, self-contained task for the subagent. It does "
                    "not share this conversation's context, so include everything it needs."
                ),
            },
            "run_in_background": {
                "type": "boolean",
                "description": (
                    "Whether to run as a background job and return its id. "
                    "Defaults to false; collect with job_output or stop with job_kill."
                ),
            },
        },
        "required": ["description", "prompt"],
    },
}

def tool_schemas() -> list[dict[str, Any]]:
    return [SUBAGENT_SCHEMA]


def dispatch(name: str, arguments: dict[str, Any], **kwargs: Any) -> str:
    if name != "subagent":
        return _error(f"unknown tool: {name}")
    return subagent(
        str(arguments.get("description") or ""),
        str(arguments.get("prompt") or ""),
        bool(arguments.get("run_in_background")),
        tool_name=name,
        **kwargs,
    )


def subagent(
    description: str,
    prompt: str,
    run_in_background: bool = False,
    tool_name: str = "subagent",
    spawn: Optional[SpawnFn] = None,
) -> str:
    """Start a child agent through the Host-injected `spawn` backend."""
    if not description.strip():
        return _error("description must be a non-empty string")
    if not prompt.strip():
        return _error("prompt must be a non-empty string")
    if spawn is None:
        return _error(
            "No subagent backend is attached. Host must inject a `spawn` "
            "callback that starts a child agent."
        )
    result = spawn(
        tool_name=tool_name,
        description=description.strip(),
        prompt=prompt,
        run_in_background=run_in_background,
    )
    return json.dumps({"success": True, **result}, ensure_ascii=False)


def _error(message: str, **details: Any) -> str:
    payload = {"success": False, "error": message}
    payload.update(details)
    return json.dumps(payload, ensure_ascii=False)
