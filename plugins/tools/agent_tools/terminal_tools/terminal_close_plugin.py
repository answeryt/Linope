# -*- coding: utf-8 -*-
"""Close a background-process terminal tab when the Host injects a closer."""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from typing import Any


PLUGIN_NAME = "terminal_close"
PLUGIN_VERSION = "1.0"

CloseFn = Callable[[str], dict[str, Any]]


def _truthy(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def tool_error(message: str) -> str:
    return json.dumps({"success": False, "error": message}, ensure_ascii=False)


def close_terminal_tool(process_id: str, close_tab: CloseFn | None = None) -> str:
    pid = (process_id or "").strip()
    if not pid:
        return tool_error("process_id is required (the background process whose tab to close).")
    if close_tab is None:
        return json.dumps(
            {
                "success": False,
                "error": "Desktop terminal tabs are unavailable until the Host injects a closer.",
                "process_id": pid,
            },
            ensure_ascii=False,
        )
    return json.dumps(close_tab(pid), ensure_ascii=False)


def check_close_terminal_requirements() -> bool:
    return _truthy("DESKTOP_APP")


CLOSE_TERMINAL_SCHEMA = {
    "name": "close_terminal",
    "description": (
        "Close the read-only terminal tab for a background process. "
        "This does not kill the process; use a process kill action for that."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "process_id": {
                "type": "string",
                "description": "Background process session id whose tab should be closed.",
            },
        },
        "required": ["process_id"],
    },
}
