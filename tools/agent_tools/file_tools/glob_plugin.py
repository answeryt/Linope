# -*- coding: utf-8 -*-
"""Find files whose paths match a glob pattern."""

from __future__ import annotations

import json
import os
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


def dispatch(name: str, arguments: dict[str, Any], **kwargs: Any) -> str:
    if name != "glob":
        return _error(f"unknown tool: {name}")
    return glob_files(str(arguments.get("pattern") or ""), arguments.get("path"), **kwargs)


def glob_files(pattern: str, path: Optional[str] = None, workspace: Optional[str] = None) -> str:
    if not pattern.strip():
        return _error("invalid pattern: expected a non-empty string")
    root = Path(workspace or os.getenv("TERMINAL_CWD") or os.getcwd())
    if path:
        candidate = Path(path)
        root = candidate if candidate.is_absolute() else root / candidate
    root = root.resolve()
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


def _error(message: str, **details: Any) -> str:
    payload = {"success": False, "error": message}
    payload.update(details)
    return json.dumps(payload, ensure_ascii=False)
