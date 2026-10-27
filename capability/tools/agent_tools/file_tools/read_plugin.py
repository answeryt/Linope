# -*- coding: utf-8 -*-
"""Read a UTF-8 text file and return line-numbered content."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional


PLUGIN_NAME = "read"
PLUGIN_VERSION = "1.0"

READ_LIMIT = 2000

READ_SCHEMA: dict[str, Any] = {
    "name": "read",
    "description": "Read a UTF-8 text file and return line-numbered content.",
    "parameters": {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Path to read, resolved by the filesystem backend.",
            },
            "offset": {
                "type": "number",
                "description": "1-based first line to return. Defaults to 1.",
            },
            "limit": {
                "type": "number",
                "description": "Maximum number of lines to return. Defaults to 2000.",
            },
        },
        "required": ["file_path"],
    },
}


def tool_schemas() -> list[dict[str, Any]]:
    return [READ_SCHEMA]



def load(kind, body, call_params=None):
    """Load one tool call. Argument shape stays in this plugin."""
    if kind != "tool":
        raise ValueError(f"This process cannot load {kind}")
    if not isinstance(body, dict):
        raise TypeError("tool content must be a mapping")
    return dispatch('read', body, **(call_params or {}))


def dispatch(name: str, arguments: dict[str, Any], **kwargs: Any) -> str:
    if name != "read":
        return _error(f"unknown tool: {name}")
    return read_file(
        str(arguments.get("file_path") or ""),
        arguments.get("offset"),
        arguments.get("limit"),
        **kwargs,
    )


def read_file(
    file_path: str,
    offset: Optional[float] = None,
    limit: Optional[float] = None,
    workspace: Optional[str] = None,
) -> str:
    try:
        path = _resolve(file_path, workspace)
    except (PermissionError, ValueError, OSError) as error:
        return _error(str(error))
    if not path.is_file():
        return _error(f"file not found: {path}")
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError:
        return _error(f"not a UTF-8 text file: {path}")
    start = 1 if offset is None else int(offset)
    if start < 1:
        return _error("offset must be a 1-based line number")
    window = READ_LIMIT if limit is None else int(limit)
    if window < 1:
        return _error("limit must be a positive integer")
    sliced = lines[start - 1 : start - 1 + window]
    numbered = "\n".join(f"{start + index:>6}|{line}" for index, line in enumerate(sliced))
    return json.dumps(
        {
            "success": True,
            "path": str(path),
            "content": numbered,
            "lineCount": len(lines),
            "returned": len(sliced),
        },
        ensure_ascii=False,
    )


def _resolve(file_path: str, workspace: Optional[str]) -> Path:
    from kernel.environment import current_room
    from kernel.environment.file_io import door_for

    return door_for(current_room(), workspace).resolve(
        file_path,
        write=False,
        base=workspace,
    )


def _error(message: str, **details: Any) -> str:
    payload = {"success": False, "error": message}
    payload.update(details)
    return json.dumps(payload, ensure_ascii=False)

def capability_profile(capability_id, changes):
    """This process leases a tool and the shared project workspace."""
    from kernel.process.profiles import tool_with_workspace

    return tool_with_workspace(capability_id, changes)

