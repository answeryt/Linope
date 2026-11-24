# -*- coding: utf-8 -*-
"""List one directory level for the desktop file window."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional


PLUGIN_NAME = "list_dir"
PLUGIN_VERSION = "1.0"

LIST_DIR_SCHEMA: dict[str, Any] = {
    "name": "list_dir",
    "description": (
        "List the files and directories directly inside one directory. "
        "Returns names and whether each entry is a file or a directory. "
        "Does not walk into subdirectories."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": (
                    "Directory to list. Defaults to the session workspace; "
                    "a relative path resolves against it."
                ),
            },
        },
        "required": [],
    },
}


def tool_schemas() -> list[dict[str, Any]]:
    return [LIST_DIR_SCHEMA]


def load(kind, body, call_params=None):
    """Load one tool call. Argument shape stays in this plugin."""
    if kind != "tool":
        raise ValueError(f"This process cannot load {kind}")
    if not isinstance(body, dict):
        raise TypeError("tool content must be a mapping")
    return dispatch("list_dir", body, **(call_params or {}))


def dispatch(name: str, arguments: dict[str, Any], **kwargs: Any) -> str:
    if name != "list_dir":
        return _error(f"unknown tool: {name}")
    return list_dir(arguments.get("path"), **kwargs)


def list_dir(path: Optional[str] = None, workspace: Optional[str] = None) -> str:
    try:
        root = _root("" if path is None else str(path), workspace)
    except (PermissionError, ValueError, OSError) as error:
        return _error(str(error))
    if not root.is_dir():
        return _error(f"directory not found: {root}")
    entries: list[dict[str, str]] = []
    try:
        children = list(root.iterdir())
    except OSError as error:
        return _error(str(error))
    children.sort(key=lambda item: (not item.is_dir(), item.name.lower()))
    for child in children:
        try:
            kind = "dir" if child.is_dir() else "file"
        except OSError:
            continue
        entries.append({"name": child.name, "kind": kind})
    return json.dumps(
        {"success": True, "path": str(root), "entries": entries},
        ensure_ascii=False,
    )


def _root(path: str, workspace: Optional[str]) -> Path:
    from kernel.environment import current_room
    from capability.sandbox.access import door_for

    door = door_for(current_room(), workspace)
    return door.resolve(path or ".", write=False, base=workspace)


def _error(message: str, **details: Any) -> str:
    payload = {"success": False, "error": message}
    payload.update(details)
    return json.dumps(payload, ensure_ascii=False)


def capability_profile(capability_id, changes):
    """This process leases a tool and the shared project workspace."""
    from capability.tools.profile import workspace_tool

    return workspace_tool(capability_id, changes, "read-only")
