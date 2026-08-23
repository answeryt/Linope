# -*- coding: utf-8 -*-
"""Create or fully replace a UTF-8 text file."""

from __future__ import annotations

import json
import os
from pathlib import Path
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


def dispatch(name: str, arguments: dict[str, Any], **kwargs: Any) -> str:
    if name != "write":
        return _error(f"unknown tool: {name}")
    return write_file(
        str(arguments.get("file_path") or ""),
        str(arguments.get("content") if arguments.get("content") is not None else ""),
        **kwargs,
    )


def write_file(file_path: str, content: str, workspace: Optional[str] = None) -> str:
    path = _resolve(file_path, workspace)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return json.dumps(
        {"success": True, "path": str(path), "bytes": len(content.encode("utf-8"))},
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
