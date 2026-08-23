# -*- coding: utf-8 -*-
"""Read the in-app terminal pane when the Host injects a callback."""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from typing import Any, Optional


PLUGIN_NAME = "terminal_read"
PLUGIN_VERSION = "1.0"

ReadCallback = Callable[..., Any]


def _truthy(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def tool_error(message: str) -> str:
    return json.dumps({"success": False, "error": message}, ensure_ascii=False)


def read_terminal_tool(
    start_line: Optional[int] = None,
    count: Optional[int] = None,
    callback: Optional[ReadCallback] = None,
) -> str:
    """Return the in-app terminal contents as a JSON string."""
    if callback is None:
        return tool_error("read_terminal is only available when a desktop pane callback is injected.")

    try:
        window = {
            key: max(floor, int(val))
            for key, val, floor in (("start", start_line, 0), ("count", count, 1))
            if val is not None
        }
    except (TypeError, ValueError):
        return tool_error("start_line and count must be integers.")

    try:
        raw = callback(**window)
    except Exception as exc:
        return tool_error(f"Failed to read terminal: {exc}")

    if not raw:
        return tool_error("No in-app terminal is open, or the read timed out.")

    try:
        return json.dumps(json.loads(raw), ensure_ascii=False)
    except (TypeError, ValueError):
        return json.dumps({"text": str(raw)}, ensure_ascii=False)


def check_read_terminal_requirements() -> bool:
    return _truthy("DESKTOP_APP")


READ_TERMINAL_SCHEMA = {
    "name": "read_terminal",
    "description": (
        "Read what is currently shown in the in-app terminal pane. "
        "Call with no arguments for the visible screen plus total_lines. "
        "Page scrollback with start_line (0 = oldest) and count."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "start_line": {
                "type": "integer",
                "description": "0-indexed first line (0 = oldest). Omit for the visible screen.",
            },
            "count": {
                "type": "integer",
                "description": "Lines to read from start_line. Defaults to the visible row count.",
            },
        },
    },
}
