# -*- coding: utf-8 -*-
"""Await-able handle for one Agent Execution.

wait / cancel are injected. This file does not import execution, gather,
or event-loop siblings. ``await task`` blocks the coroutine, not an OS
thread.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable, Mapping
from typing import Any
from uuid import uuid4


PLUGIN_NAME = "kernel_async_task"
PLUGIN_VERSION = "1.0"

Wait = Callable[..., Any]
Cancel = Callable[..., Any]


async def _call(func: Callable[..., Any] | None, *args: Any, **kwargs: Any) -> Any:
    if func is None:
        return None
    result = func(*args, **kwargs)
    if inspect.isawaitable(result):
        return await result
    return result


def _new_id() -> str:
    return uuid4().hex


def _default_record(**fields: Any) -> dict[str, Any]:
    execution_id = fields.pop("execution_id", None) or _new_id()
    record = {
        "task_id": fields.pop("task_id", None) or execution_id,
        "process_id": fields.pop("process_id", None),
        "execution_id": execution_id,
        "thread_id": fields.pop("thread_id", None),
        "state": fields.pop("state", "ready"),
        "context": dict(fields.pop("context", None) or {}),
        "parent_id": fields.pop("parent_id", None),
        "children": list(fields.pop("children", None) or ()),
        "budget": dict(fields.pop("budget", None) or {}),
        "events": list(fields.pop("events", None) or ()),
        "agent": fields.pop("agent", None),
        "goal": fields.pop("goal", None),
        "wait_reason": fields.pop("wait_reason", None),
        "priority": int(fields.pop("priority", 0) or 0),
    }
    record.update(fields)
    return record


class AgentTask:
    """Logical task handle. Host injects wait to join the execution."""

    def __init__(
        self,
        record: Mapping[str, Any],
        *,
        wait: Wait | None = None,
        cancel: Cancel | None = None,
    ) -> None:
        if record is None:
            raise TypeError("record is required")
        self.record = dict(record)
        self._wait = wait
        self._cancel = cancel
        self._result: Any = None
        self._done = False
        self._cancelled = False

    @property
    def task_id(self) -> str | None:
        value = self.record.get("task_id")
        return None if value is None else str(value)

    @property
    def process_id(self) -> str | None:
        value = self.record.get("process_id")
        return None if value is None else str(value)

    @property
    def execution_id(self) -> str | None:
        value = self.record.get("execution_id")
        return None if value is None else str(value)

    @property
    def state(self) -> str:
        return str(self.record.get("state") or "")

    @property
    def done(self) -> bool:
        return self._done

    def __await__(self) -> Any:
        return self._join().__await__()

    async def _join(self) -> Any:
        if self._cancelled:
            raise asyncio_cancelled()
        if self._done:
            return self._result
        if self._wait is None:
            raise RuntimeError("Host must inject wait")
        self._result = await _call(self._wait, self)
        self._done = True
        self.record["state"] = "done"
        self.record["result"] = self._result
        return self._result

    async def cancel(self) -> None:
        self._cancelled = True
        self.record["state"] = "cancelled"
        await _call(self._cancel, self)


def asyncio_cancelled() -> BaseException:
    import asyncio

    return asyncio.CancelledError()


def create_agent_task(
    *,
    agent: str | None = None,
    goal: str | None = None,
    process_id: str | None = None,
    wait: Wait | None = None,
    cancel: Cancel | None = None,
    record: Mapping[str, Any] | None = None,
    **fields: Any,
) -> AgentTask:
    """Build an AgentTask. Host injects wait so ``await task`` can join."""
    if record is None:
        payload = _default_record(agent=agent, goal=goal, process_id=process_id, **fields)
    else:
        payload = dict(record)
        if agent is not None:
            payload["agent"] = agent
        if goal is not None:
            payload["goal"] = goal
        if process_id is not None:
            payload["process_id"] = process_id
        payload.update(fields)
    return AgentTask(payload, wait=wait, cancel=cancel)
