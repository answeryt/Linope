# -*- coding: utf-8 -*-
"""Send a follow-up message to a background subagent."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any, Optional


PLUGIN_NAME = "send_message"
PLUGIN_VERSION = "1.0"

ControlFn = Callable[..., dict[str, Any]]

SEND_MESSAGE_SCHEMA: dict[str, Any] = {
    "name": "send_message",
    "description": (
        "Send a message to a background subagent by its subagent id, continuing "
        "the same conversation. This call returns no answer from the subagent — "
        "only confirmation that the message was delivered."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "subagent_id": {
                "type": "string",
                "description": "The subagent id returned when the background subagent was started.",
            },
            "message": {
                "type": "string",
                "description": "The message to deliver to the subagent.",
            },
        },
        "required": ["subagent_id", "message"],
    },
}


def tool_schemas() -> list[dict[str, Any]]:
    return [SEND_MESSAGE_SCHEMA]


def dispatch(name: str, arguments: dict[str, Any], **kwargs: Any) -> str:
    if name != "send_message":
        return _error(f"unknown tool: {name}")
    subagent_id = str(arguments.get("subagent_id") or "").strip()
    message = str(arguments.get("message") or "").strip()
    if not subagent_id or not message:
        return _error("subagent_id and message are required")
    control: Optional[ControlFn] = kwargs.get("control")
    if control is None:
        return _error("Host must inject a `control` callback.")
    result = control(action="send_message", subagent_id=subagent_id, message=message)
    return json.dumps({"success": True, **result}, ensure_ascii=False)


def _error(message: str, **details: Any) -> str:
    payload = {"success": False, "error": message}
    payload.update(details)
    return json.dumps(payload, ensure_ascii=False)
