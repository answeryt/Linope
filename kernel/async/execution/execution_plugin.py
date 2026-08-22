# -*- coding: utf-8 -*-
"""One Agent Execution record: a runnable unit inside a process.

Not an OS thread. Host and the task handle accept Mapping and do not
import this file.
"""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from typing import Any
from uuid import uuid4


PLUGIN_NAME = "kernel_async_execution"
PLUGIN_VERSION = "1.0"

TASK_ID = "task_id"
PROCESS_ID = "process_id"
EXECUTION_ID = "execution_id"
THREAD_ID = "thread_id"
STATE = "state"
CONTEXT = "context"
PARENT_ID = "parent_id"
CHILDREN = "children"
BUDGET = "budget"
EVENTS = "events"
AGENT = "agent"
GOAL = "goal"
WAIT_REASON = "wait_reason"
PRIORITY = "priority"
RESULT = "result"


def new_execution_id() -> str:
    return uuid4().hex


def build_execution(
    *,
    agent: str | None = None,
    goal: str | None = None,
    process_id: str | None = None,
    task_id: str | None = None,
    execution_id: str | None = None,
    thread_id: str | None = None,
    state: str = "ready",
    parent_id: str | None = None,
    children: list[str] | tuple[str, ...] | None = None,
    budget: Mapping[str, Any] | None = None,
    context: Mapping[str, Any] | None = None,
    events: list[Any] | tuple[Any, ...] | None = None,
    wait_reason: str | None = None,
    priority: int = 0,
    **fields: Any,
) -> dict[str, Any]:
    eid = execution_id or new_execution_id()
    record: MutableMapping[str, Any] = {
        TASK_ID: task_id or eid,
        PROCESS_ID: process_id,
        EXECUTION_ID: eid,
        THREAD_ID: thread_id,
        STATE: state,
        CONTEXT: dict(context or {}),
        PARENT_ID: parent_id,
        CHILDREN: list(children or ()),
        BUDGET: dict(budget or {}),
        EVENTS: list(events or ()),
        AGENT: agent,
        GOAL: goal,
        WAIT_REASON: wait_reason,
        PRIORITY: int(priority),
    }
    record.update(fields)
    return dict(record)


def attach_event(record: Mapping[str, Any], event: Mapping[str, Any]) -> dict[str, Any]:
    events = list(record.get(EVENTS) or ())
    events.append(dict(event))
    updated = dict(record)
    updated[EVENTS] = events
    return updated


def attach_child(record: Mapping[str, Any], child_id: str) -> dict[str, Any]:
    children = list(record.get(CHILDREN) or ())
    if child_id not in children:
        children.append(child_id)
    updated = dict(record)
    updated[CHILDREN] = children
    return updated
