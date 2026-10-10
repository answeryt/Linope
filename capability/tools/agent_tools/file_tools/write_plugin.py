# -*- coding: utf-8 -*-
"""Create or fully replace a UTF-8 text file."""

from __future__ import annotations

import json
from typing import Any, Optional


PLUGIN_NAME = "write"
PLUGIN_VERSION = "1.0"

WRITE_SCHEMA: dict[str, Any] = {
    "name": "write",
    "description": "Create or fully replace a UTF-8 text file.",
    "parameters": {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Path to write, resolved by the filesystem backend.",
            },
            "content": {
                "type": "string",
                "description": "Full UTF-8 text content to write.",
            },
        },
        "required": ["file_path", "content"],
    },
}


def tool_schemas() -> list[dict[str, Any]]:
    return [WRITE_SCHEMA]



def load(kind, body, call_params=None):
    """Load one tool call. Argument shape stays in this plugin."""
    if kind != "tool":
        raise ValueError(f"这个进程不能装入 {kind}")
    if not isinstance(body, dict):
        raise TypeError("tool 的内容必须是映射")
    return dispatch('write', body, **(call_params or {}))


def dispatch(name: str, arguments: dict[str, Any], **kwargs: Any) -> str:
    if name != "write":
        return _error(f"unknown tool: {name}")
    return write_file(
        str(arguments.get("file_path") or ""),
        str(arguments.get("content") if arguments.get("content") is not None else ""),
        **kwargs,
    )


def write_file(file_path: str, content: str, workspace: Optional[str] = None) -> str:
    from kernel.environment import current_room
    from kernel.environment.file_io import door_for

    try:
        path = door_for(current_room(), workspace).write_text(
            file_path,
            content,
            base=workspace,
        )
    except (PermissionError, ValueError, OSError) as error:
        return _error(str(error))
    return json.dumps(
        {"success": True, "path": str(path), "bytes": len(content.encode("utf-8"))},
        ensure_ascii=False,
    )


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

