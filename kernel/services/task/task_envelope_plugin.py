# -*- coding: utf-8 -*-
"""Task envelope for the agent microservice.

One incoming task is one agent-loop session. Host builds these mappings
before they reach the subscriber; other plugins accept Mapping and do
not import this file.
"""

from __future__ import annotations

from typing import Any, Mapping, MutableMapping
from uuid import uuid4


PLUGIN_NAME = "kernel_task_envelope"
PLUGIN_VERSION = "1.0"

TASK_ID = "task_id"
SESSION_ID = "session_id"
USER_MESSAGE = "user_message"
TOOLS = "tools"
SKILLS = "skills"
MODEL = "model"
CANCEL_AFTER = "cancel_after"
MESSAGE_ID = "message_id"


def new_task_id() -> str:
    return uuid4().hex


def normalize_task(payload: Mapping[str, Any] | str, *, message_id: str | None = None) -> dict[str, Any]:
    """Turn a stream payload into a task mapping."""
    if isinstance(payload, str):
        task: dict[str, Any] = {USER_MESSAGE: payload}
    else:
        task = dict(payload)
    if USER_MESSAGE not in task:
        raise ValueError("task is missing user_message")
    task.setdefault(TASK_ID, message_id or new_task_id())
    task.setdefault(SESSION_ID, task[TASK_ID])
    task.setdefault(TOOLS, ())
    task.setdefault(SKILLS, ())
    if message_id:
        task[MESSAGE_ID] = message_id
    return task


def event(event_type: str, task: Mapping[str, Any], **fields: Any) -> dict[str, Any]:
    """Build an outbound event for agent.events.{task_id}."""
    payload: dict[str, Any] = {
        "type": event_type,
        TASK_ID: task.get(TASK_ID),
        SESSION_ID: task.get(SESSION_ID),
    }
    payload.update(fields)
    return payload


def result(task: Mapping[str, Any], *, status: str, content: str = "", **fields: Any) -> dict[str, Any]:
    payload: MutableMapping[str, Any] = {
        TASK_ID: task.get(TASK_ID),
        SESSION_ID: task.get(SESSION_ID),
        "status": status,
        "content": content,
    }
    payload.update(fields)
    return dict(payload)
