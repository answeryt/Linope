# -*- coding: utf-8 -*-
"""Whole-list todo replacement. Each call replaces the previous session list."""

from __future__ import annotations

import json
import os
import threading
from typing import Any, Optional


PLUGIN_NAME = "todo"
PLUGIN_VERSION = "1.0"

STATUSES = ("pending", "in_progress", "completed")
ALLOW_PARALLEL = os.getenv("TODO_ALLOW_PARALLEL", "true").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}

_STORE: dict[str, list[dict[str, str]]] = {}
_LOCK = threading.Lock()

DESCRIPTION_HEAD = (
    "Record and update a structured task list for the current work. Send the ENTIRE "
    "list every call — it REPLACES the previous list (there are no partial updates, "
    "no per-item edits). Use it to plan multi-step work and show progress: add one "
    "todo per concrete step before you start. "
)
DESCRIPTION_PARALLEL = (
    "Mark every todo being actively worked on `in_progress` — several at once when "
    "work genuinely runs in parallel (e.g. concurrent subagents or background "
    "commands), one for sequential work; while work remains, at least one task "
    "should be `in_progress`. "
)
DESCRIPTION_SINGLE = (
    "Keep AT MOST ONE todo `in_progress` at a time; while work remains, exactly "
    "one active task should be `in_progress`. "
)
DESCRIPTION_TAIL = (
    "Mark a todo `completed` the moment it is done (do not batch completions), "
    "and allow no `in_progress` item only once all work is complete. Skip the "
    "list for trivial single-step tasks. Statuses: `pending` (not started), "
    "`in_progress` (being worked on now), `completed` (finished)."
)


TODO_SCHEMA: dict[str, Any] = {
    "name": "todo_write",
    "description": DESCRIPTION_HEAD
    + (DESCRIPTION_PARALLEL if ALLOW_PARALLEL else DESCRIPTION_SINGLE)
    + DESCRIPTION_TAIL,
    "parameters": {
        "type": "object",
        "properties": {
            "todos": {
                "type": "array",
                "description": "The COMPLETE task list, replacing any previous list.",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "content": {
                            "type": "string",
                            "description": "What the task is — a short imperative line.",
                        },
                        "status": {
                            "type": "string",
                            "enum": list(STATUSES),
                            "description": "pending (not started) | in_progress (now) | completed (done).",
                        },
                    },
                    "required": ["content", "status"],
                },
            },
        },
        "required": ["todos"],
    },
}


def tool_schemas() -> list[dict[str, Any]]:
    return [TODO_SCHEMA]



def load(kind, body, call_params=None):
    """Load one tool call. Argument shape stays in this plugin."""
    if kind != "tool":
        raise ValueError(f"这个进程不能装入 {kind}")
    if not isinstance(body, dict):
        raise TypeError("tool 的内容必须是映射")
    return dispatch('todo_write', body, **(call_params or {}))


def dispatch(name: str, arguments: dict[str, Any], **kwargs: Any) -> str:
    if name != "todo_write":
        return _error(f"unknown tool: {name}")
    return todo_write(arguments.get("todos") or [], **kwargs)


def todo_write(
    todos: list[Any],
    session_id: Optional[str] = None,
    allow_parallel: bool = ALLOW_PARALLEL,
) -> str:
    """Replace the session todo list with `todos`."""
    try:
        canonical = _canonicalize(todos, allow_parallel)
    except ValueError as exc:
        return _error(str(exc))
    key = session_id or "default"
    with _LOCK:
        _STORE[key] = canonical
    counts = {
        "pending": sum(1 for item in canonical if item["status"] == "pending"),
        "inProgress": sum(1 for item in canonical if item["status"] == "in_progress"),
        "completed": sum(1 for item in canonical if item["status"] == "completed"),
    }
    return json.dumps({"success": True, "todos": canonical, "counts": counts}, ensure_ascii=False)


def _canonicalize(raw: list[Any], allow_parallel: bool) -> list[dict[str, str]]:
    if not isinstance(raw, list):
        raise ValueError("todos must be an array")
    todos: list[dict[str, str]] = []
    seen: set[str] = set()
    active = 0
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError("invalid todo: expected an object")
        content = str(item.get("content") or "").strip()
        status = str(item.get("status") or "")
        if not content:
            raise ValueError("invalid todo: `content` must be a non-empty string")
        if status not in STATUSES:
            raise ValueError(f"invalid todo status: {status}")
        if content in seen:
            raise ValueError(f"invalid todos: duplicate content {content!r}")
        seen.add(content)
        if status == "in_progress":
            active += 1
        todos.append({"content": content, "status": status})
    if not allow_parallel and active > 1:
        raise ValueError(f"invalid todos: at most one task may be in_progress (got {active})")
    return todos


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

