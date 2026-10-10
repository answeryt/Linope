# -*- coding: utf-8 -*-
"""Edit an existing UTF-8 text file by replacing literal text."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional


PLUGIN_NAME = "edit"
PLUGIN_VERSION = "1.0"

EDIT_SCHEMA: dict[str, Any] = {
    "name": "edit",
    "description": "Edit an existing UTF-8 text file by replacing literal text.",
    "parameters": {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Path to edit, resolved by the filesystem backend.",
            },
            "old_string": {
                "type": "string",
                "description": "Literal text to replace. Must match exactly.",
            },
            "new_string": {
                "type": "string",
                "description": "Literal replacement text. Use an empty string to delete the match.",
            },
            "replace_all": {
                "type": "boolean",
                "description": (
                    "Replace all matches. Defaults to false; when false, "
                    "old_string must appear exactly once."
                ),
            },
        },
        "required": ["file_path", "old_string", "new_string"],
    },
}


def tool_schemas() -> list[dict[str, Any]]:
    return [EDIT_SCHEMA]



def load(kind, body, call_params=None):
    """Load one tool call. Argument shape stays in this plugin."""
    if kind != "tool":
        raise ValueError(f"这个进程不能装入 {kind}")
    if not isinstance(body, dict):
        raise TypeError("tool 的内容必须是映射")
    return dispatch('edit', body, **(call_params or {}))


def dispatch(name: str, arguments: dict[str, Any], **kwargs: Any) -> str:
    if name != "edit":
        return _error(f"unknown tool: {name}")
    return edit_file(
        str(arguments.get("file_path") or ""),
        str(arguments.get("old_string") if arguments.get("old_string") is not None else ""),
        str(arguments.get("new_string") if arguments.get("new_string") is not None else ""),
        bool(arguments.get("replace_all")),
        **kwargs,
    )


def edit_file(
    file_path: str,
    old_string: str,
    new_string: str,
    replace_all: bool = False,
    workspace: Optional[str] = None,
) -> str:
    path = _resolve(file_path, workspace)
    if not path.is_file():
        return _error(f"file not found: {path}")
    text = path.read_text(encoding="utf-8")
    count = text.count(old_string)
    if count == 0:
        return _error("old_string not found")
    if not replace_all and count != 1:
        return _error(f"old_string must appear exactly once (found {count})")
    updated = text.replace(old_string, new_string) if replace_all else text.replace(old_string, new_string, 1)
    path.write_text(updated, encoding="utf-8")
    return json.dumps(
        {"success": True, "path": str(path), "replacements": count if replace_all else 1},
        ensure_ascii=False,
    )


def _resolve(file_path: str, workspace: Optional[str]) -> Path:
    root = Path(workspace or os.getenv("TERMINAL_CWD") or os.getcwd())
    candidate = Path(file_path)
    if not candidate.is_absolute():
        candidate = root / candidate
    return candidate.resolve()


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

