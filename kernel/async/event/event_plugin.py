# -*- coding: utf-8 -*-
"""Event mapping for the Agent Event Loop.

Host and dispatch accept Mapping and do not import this file. One event
wakes the scheduler; it is not a queue message for a new agent session.
"""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from typing import Any
from uuid import uuid4


PLUGIN_NAME = "kernel_async_event"
PLUGIN_VERSION = "1.0"

USER_MESSAGE = "user.message"
LLM_CALL = "llm.call"
LLM_RESPONSE = "llm.response"
TOOL_CALL = "tool.call"
TOOL_RESULT = "tool.result"
TASK_SPAWN = "task.spawn"
TASK_DONE = "task.done"
HUMAN_WAIT = "human.wait"
HUMAN_RESUME = "human.resume"
EXECUTION_SUSPEND = "execution.suspend"
EXECUTION_RUN = "execution.run"
STOP = "_stop"


def new_event_id() -> str:
    return uuid4().hex


def event(event_type: str, **fields: Any) -> dict[str, Any]:
    """Build an outbound event. Extra fields are copied onto the record."""
    if not event_type:
        raise ValueError("event_type is required")
    payload: MutableMapping[str, Any] = {
        "type": event_type,
        "event_id": fields.pop("event_id", None) or new_event_id(),
    }
    payload.update(fields)
    return dict(payload)


def event_type(record: Mapping[str, Any]) -> str:
    return str(record.get("type") or "")
