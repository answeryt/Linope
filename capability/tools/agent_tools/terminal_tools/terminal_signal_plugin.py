# -*- coding: utf-8 -*-
"""Send an allowed signal to a persistent terminal's foreground process group."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any, Optional


PLUGIN_NAME = "terminal_signal"
PLUGIN_VERSION = "1.0"

BackendFn = Callable[..., dict[str, Any]]
SIGNALS = ("SIGINT", "SIGTERM", "SIGKILL", "SIGTSTP", "SIGHUP")

TERMINAL_SIGNAL_SCHEMA: dict[str, Any] = {
    "name": "terminal_signal",
    "description": (
        "Send an allowed signal to the current foreground process group of a "
        "persistent terminal."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "sessionId": {"type": "string", "description": "Terminal session id."},
            "signal": {
                "type": "string",
                "enum": list(SIGNALS),
                "description": "Signal to deliver. Shell-targeted SIGKILL is rejected; use terminal_close.",
            },
        },
        "required": ["sessionId", "signal"],
    },
}


def tool_schemas() -> list[dict[str, Any]]:
    return [TERMINAL_SIGNAL_SCHEMA]



def load(kind, body, call_params=None):
    """Load one tool call. Argument shape stays in this plugin."""
    if kind != "tool":
        raise ValueError(f"这个进程不能装入 {kind}")
    if not isinstance(body, dict):
        raise TypeError("tool 的内容必须是映射")
    return dispatch('terminal_signal', body, **(call_params or {}))


def dispatch(name: str, arguments: dict[str, Any], **kwargs: Any) -> str:
    if name != "terminal_signal":
        return _error(f"unknown tool: {name}")
    return terminal_signal(
        str(arguments.get("sessionId") or ""),
        str(arguments.get("signal") or ""),
        **kwargs,
    )


def terminal_signal(
    session_id: str,
    signal: str,
    backend: Optional[BackendFn] = None,
) -> str:
    if not session_id.strip():
        return _error("sessionId is required")
    if signal not in SIGNALS:
        return _error(f"unknown signal: {signal}")
    if signal == "SIGKILL":
        return _error("Shell-targeted SIGKILL is rejected; use terminal_close.")
    if backend is None:
        return _error("Host must inject a persistent terminal `backend`.")
    result = backend(action="terminal_signal", sessionId=session_id, signal=signal)
    return json.dumps({"success": True, **result}, ensure_ascii=False)


def _error(message: str, **details: Any) -> str:
    payload = {"success": False, "error": message}
    payload.update(details)
    return json.dumps(payload, ensure_ascii=False)

def capability_profile(capability_id, changes):
    """This process leases a tool and the shared project workspace."""
    from kernel.process.profiles import tool_with_workspace

    return tool_with_workspace(capability_id, changes)

