# -*- coding: utf-8 -*-
"""Find files whose paths match a glob pattern."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional


PLUGIN_NAME = "glob"
PLUGIN_VERSION = "1.0"

GLOB_MAX_RESULTS = 100
VCS_EXCLUDES = {".git", ".hg", ".svn"}

GLOB_SCHEMA: dict[str, Any] = {
    "name": "glob",
    "description": (
        "Find files whose paths match a glob pattern. Returns matching file "
        "paths — never directories — including hidden and ignored files "
        "(VCS metadata directories are excluded). Up to 100 paths come back "
        "in modification-time order."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": (
                    'Glob pattern to match file paths against (e.g. "**/*.ts"). '
                    'A pattern with no "/" matches the basename at any depth.'
                ),
            },
            "path": {
                "type": "string",
                "description": (
                    "Directory to search in. Defaults to the session workspace; "
                    "a relative path resolves against it."
                ),
            },
        },
        "required": ["pattern"],
    },
}


def tool_schemas() -> list[dict[str, Any]]:
    return [GLOB_SCHEMA]



def load(kind, body, call_params=None):
    """Load one tool call. Argument shape stays in this plugin."""
    if kind != "tool":
        raise ValueError(f"This process cannot load {kind}")
    if not isinstance(body, dict):
        raise TypeError("tool content must be a mapping")
    return dispatch('glob', body, **(call_params or {}))


def dispatch(name: str, arguments: dict[str, Any], **kwargs: Any) -> str:
    if name != "glob":
        return _error(f"unknown tool: {name}")
    return glob_files(str(arguments.get("pattern") or ""), arguments.get("path"), **kwargs)


def glob_files(pattern: str, path: Optional[str] = None, workspace: Optional[str] = None) -> str:
    if not pattern.strip():
        return _error("invalid pattern: expected a non-empty string")
    try:
        root = _root(path, workspace)
    except (PermissionError, ValueError, OSError) as error:
        return _error(str(error))
    if not root.is_dir():
        return _error(f"directory not found: {root}")
    query = pattern if "/" in pattern or "\\" in pattern else f"**/{pattern}"
    matches: list[tuple[float, str]] = []
    for item in root.glob(query):
        if not item.is_file() or any(part in VCS_EXCLUDES for part in item.parts):
            continue
        matches.append((item.stat().st_mtime, item.relative_to(root).as_posix()))
    matches.sort(key=lambda row: row[0], reverse=True)
    paths = [row[1] for row in matches[:GLOB_MAX_RESULTS]]
    return json.dumps(
        {
            "success": True,
            "path": str(root),
            "files": paths,
            "count": len(paths),
            "truncated": len(matches) > GLOB_MAX_RESULTS,
            "total": len(matches),
        },
        ensure_ascii=False,
    )


def _root(path: Optional[str], workspace: Optional[str]) -> Path:
    from kernel.environment import current_room
    from kernel.environment.file_io import door_for

    door = door_for(current_room(), workspace)
    return door.resolve(path or ".", write=False, base=workspace)


def _error(message: str, **details: Any) -> str:
    payload = {"success": False, "error": message}
    payload.update(details)
    return json.dumps(payload, ensure_ascii=False)

def capability_profile(capability_id, changes):
    """This process leases a tool and the shared project workspace."""
    from kernel.process.profiles import tool_with_workspace

    return tool_with_workspace(capability_id, changes)

