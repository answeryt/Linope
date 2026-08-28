# -*- coding: utf-8 -*-
"""Send text to a persistent terminal session."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any, Optional


PLUGIN_NAME = "terminal_send"
PLUGIN_VERSION = "1.0"

BackendFn = Callable[..., dict[str, Any]]

TERMINAL_SEND_SCHEMA: dict[str, Any] = {
    "name": "terminal_send",
    "description": (
        "Send text to a persistent terminal. By default Enter is submitted and "
        "the call waits for a prompt, stdin wait, output silence, timeout, or "
        "session exit. Background mode returns a job id for job_output/job_kill."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "sessionId": {
                "type": "string",
                "description": "Terminal session id returned by terminal_open or terminal_list.",
            },
            "text": {
                "type": "string",
                "description": "UTF-8 text to write to the terminal.",
            },
            "submit": {
                "type": "boolean",
                "description": (
                    "Submit Enter after text (default true). Set false for "
                    "control characters or incomplete REPL input."
                ),
            },
            "run_in_background": {
                "type": "boolean",
                "description": "Return a job id immediately; collect with job_output or stop with job_kill.",
            },
        },
        "required": ["sessionId", "text"],
    },
}


def tool_schemas() -> list[dict[str, Any]]:
    return [TERMINAL_SEND_SCHEMA]


def dispatch(name: str, arguments: dict[str, Any], **kwargs: Any) -> str:
    if name != "terminal_send":
        return _error(f"unknown tool: {name}")
    return terminal_send(
        str(arguments.get("sessionId") or ""),
        str(arguments.get("text") if arguments.get("text") is not None else ""),
        arguments.get("submit"),
        bool(arguments.get("run_in_background")),
        **kwargs,
    )


def terminal_send(
    session_id: str,
    text: str,
    submit: Optional[bool] = None,
    run_in_background: bool = False,
    backend: Optional[BackendFn] = None,
) -> str:
    if not session_id.strip():
        return _error("sessionId is required")
    if backend is None:
        return _error("Host must inject a persistent terminal `backend`.")
    result = backend(
        action="terminal_send",
        sessionId=session_id,
        text=text,
        submit=True if submit is None else submit,
        run_in_background=run_in_background,
    )
    return json.dumps({"success": True, **result}, ensure_ascii=False)


def _error(message: str, **details: Any) -> str:
    payload = {"success": False, "error": message}
    payload.update(details)
    return json.dumps(payload, ensure_ascii=False)
