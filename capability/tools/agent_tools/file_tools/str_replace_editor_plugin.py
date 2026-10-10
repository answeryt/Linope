# -*- coding: utf-8 -*-
"""Harness-compatible view / create / unique literal replace / line-insert editor."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional


PLUGIN_NAME = "str_replace_editor"
PLUGIN_VERSION = "1.0"

MAX_OUTPUT_CHARS = 16_000
TRUNCATED_MESSAGE = (
    "<response clipped><NOTE>To save on context only part of this file has been "
    "shown to you. You should retry this tool after you have searched inside the "
    "file with `grep -n` in order to find the line numbers of what you are looking for.</NOTE>"
)

EDITOR_SCHEMA: dict[str, Any] = {
    "name": "str_replace_editor",
    "description": (
        "Custom editing tool for viewing, creating and editing files. "
        "If `path` is a file, `view` displays `cat -n` output. If `path` is a "
        "directory, `view` lists non-hidden files and directories up to 2 levels deep. "
        "`create` fails when the path already exists as a file. "
        "`str_replace` requires `old_str` to match exactly once unless it is unique context."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "enum": ["view", "create", "str_replace", "insert"],
                "description": "The commands to run. Allowed options are: `view`, `create`, `str_replace`, `insert`.",
            },
            "path": {
                "type": "string",
                "description": "Absolute path to file or directory, e.g. `/repo/file.py` or `/repo`.",
            },
            "file_text": {
                "type": "string",
                "description": "Required parameter of `create` command, with the content of the file to be created.",
            },
            "insert_line": {
                "type": "integer",
                "description": "Required parameter of `insert`. `new_str` is inserted AFTER this line.",
            },
            "new_str": {
                "type": "string",
                "description": "Replacement or insert text.",
            },
            "old_str": {
                "type": "string",
                "description": "Required parameter of `str_replace` containing the string in `path` to replace.",
            },
            "view_range": {
                "type": "array",
                "items": {"type": "integer"},
                "description": (
                    "Optional `view` line range, e.g. [11, 12]. Indexing starts at 1. "
                    "`[start_line, -1]` shows through the end of the file."
                ),
            },
        },
        "required": ["command", "path"],
    },
}


def tool_schemas() -> list[dict[str, Any]]:
    return [EDITOR_SCHEMA]



def load(kind, body, call_params=None):
    """Load one tool call. Argument shape stays in this plugin."""
    if kind != "tool":
        raise ValueError(f"这个进程不能装入 {kind}")
    if not isinstance(body, dict):
        raise TypeError("tool 的内容必须是映射")
    return dispatch('str_replace_editor', body, **(call_params or {}))


def dispatch(name: str, arguments: dict[str, Any], **kwargs: Any) -> str:
    if name != "str_replace_editor":
        return _error(f"unknown tool: {name}")
    return str_replace_editor(
        command=str(arguments.get("command") or ""),
        path=str(arguments.get("path") or ""),
        file_text=arguments.get("file_text"),
        insert_line=arguments.get("insert_line"),
        new_str=arguments.get("new_str"),
        old_str=arguments.get("old_str"),
        view_range=arguments.get("view_range"),
        **kwargs,
    )


def str_replace_editor(
    command: str,
    path: str,
    file_text: Optional[str] = None,
    insert_line: Optional[int] = None,
    new_str: Optional[str] = None,
    old_str: Optional[str] = None,
    view_range: Optional[list[int]] = None,
    workspace: Optional[str] = None,
    max_output_chars: int = MAX_OUTPUT_CHARS,
) -> str:
    """View, create, replace, or insert in a file."""
    target = _resolve(path, workspace)
    if command == "view":
        return _view(target, view_range, max_output_chars)
    if command == "create":
        if file_text is None:
            return _error("create requires file_text")
        if target.is_file():
            return _error(f"create refused: file already exists: {target}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(file_text, encoding="utf-8")
        return json.dumps({"success": True, "path": str(target), "command": "create"}, ensure_ascii=False)
    if command == "str_replace":
        if old_str is None:
            return _error("str_replace requires old_str")
        return _replace(target, old_str, new_str or "")
    if command == "insert":
        if insert_line is None or new_str is None:
            return _error("insert requires insert_line and new_str")
        return _insert(target, int(insert_line), new_str)
    return _error(f"unknown command: {command}")


def _view(target: Path, view_range: Optional[list[int]], max_output_chars: int) -> str:
    if target.is_dir():
        entries = _list_shallow(target)
        return json.dumps({"success": True, "path": str(target), "listing": entries}, ensure_ascii=False)
    if not target.is_file():
        return _error(f"path not found: {target}")
    lines = target.read_text(encoding="utf-8").splitlines()
    start, end = 1, len(lines)
    if view_range:
        if len(view_range) != 2:
            return _error("view_range must be [start, end]")
        start = int(view_range[0])
        end = len(lines) if int(view_range[1]) == -1 else int(view_range[1])
    sliced = lines[max(start, 1) - 1 : max(end, 0)]
    numbered = "\n".join(f"{start + index:>6}|{line}" for index, line in enumerate(sliced))
    if len(numbered) > max_output_chars:
        numbered = numbered[:max_output_chars] + TRUNCATED_MESSAGE
    return json.dumps({"success": True, "path": str(target), "content": numbered}, ensure_ascii=False)


def _replace(target: Path, old_str: str, new_str: str) -> str:
    if not target.is_file():
        return _error(f"file not found: {target}")
    text = target.read_text(encoding="utf-8")
    count = text.count(old_str)
    if count == 0:
        return _error("old_str not found")
    if count != 1:
        return _error(f"old_str is not unique (found {count} matches)")
    target.write_text(text.replace(old_str, new_str, 1), encoding="utf-8")
    return json.dumps({"success": True, "path": str(target), "command": "str_replace"}, ensure_ascii=False)


def _insert(target: Path, insert_line: int, new_str: str) -> str:
    if not target.is_file():
        return _error(f"file not found: {target}")
    lines = target.read_text(encoding="utf-8").splitlines(keepends=True)
    if insert_line < 0 or insert_line > len(lines):
        return _error(f"insert_line out of range: {insert_line}")
    insertion = new_str if new_str.endswith("\n") else new_str + "\n"
    lines.insert(insert_line, insertion)
    target.write_text("".join(lines), encoding="utf-8")
    return json.dumps({"success": True, "path": str(target), "command": "insert"}, ensure_ascii=False)


def _list_shallow(root: Path) -> list[str]:
    rows: list[str] = []
    for child in sorted(root.iterdir(), key=lambda item: item.name.lower()):
        if child.name.startswith("."):
            continue
        rows.append(child.name + ("/" if child.is_dir() else ""))
        if child.is_dir():
            for nested in sorted(child.iterdir(), key=lambda item: item.name.lower()):
                if nested.name.startswith("."):
                    continue
                rows.append(f"  {nested.name}" + ("/" if nested.is_dir() else ""))
    return rows


def _resolve(path: str, workspace: Optional[str]) -> Path:
    candidate = Path(path)
    if not candidate.is_absolute():
        root = Path(workspace or os.getenv("TERMINAL_CWD") or os.getcwd())
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

