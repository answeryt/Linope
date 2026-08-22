# -*- coding: utf-8 -*-
"""Injected composition root for the Agent Async Runtime.

Factories are injected: this file must not import process, thred, or
async siblings. Missing factories fall back to in-memory mappings so a
Host can wire incrementally.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable, Mapping
from typing import Any
from uuid import uuid4


PLUGIN_NAME = "kernel_async_runtime"
PLUGIN_VERSION = "1.0"

CreateProcess = Callable[..., Any]
CreateTask = Callable[..., Any]
Gather = Callable[..., Any]
Emit = Callable[..., Any]
Spawn = Callable[..., Any]


async def _call(func: Callable[..., Any] | None, *args: Any, **kwargs: Any) -> Any:
    if func is None:
        return None
    result = func(*args, **kwargs)
    if inspect.isawaitable(result):
        return await result
    return result


def _new_id() -> str:
    return uuid4().hex


class AgentProcessHandle:
    """Handle returned by create_process. create_task is injected."""

    def __init__(
        self,
        record: Mapping[str, Any],
        *,
        create_task: CreateTask | None = None,
        spawn: Spawn | None = None,
    ) -> None:
        self.record = dict(record)
        self._create_task = create_task
        self._spawn = spawn

    @property
    def process_id(self) -> str | None:
        value = self.record.get("process_id")
        return None if value is None else str(value)

    @property
    def agent(self) -> str | None:
        value = self.record.get("agent")
        return None if value is None else str(value)

    def create_task(self, **fields: Any) -> Any:
        if self._create_task is None:
            raise RuntimeError("Host must inject create_task")
        fields.setdefault("process_id", self.process_id)
        return self._create_task(**fields)

    def spawn(self, *, agent: str, **fields: Any) -> Any:
        if self._spawn is None:
            raise RuntimeError("Host must inject spawn")
        fields.setdefault("parent_id", self.process_id)
        return self._spawn(self.process_id, agent=agent, **fields)


class AgentRuntime:
    """create_process / create_task / gather over an injected event loop."""

    def __init__(
        self,
        *,
        create_process: CreateProcess | None = None,
        create_task: CreateTask | None = None,
        gather: Gather | None = None,
        emit: Emit | None = None,
        spawn: Spawn | None = None,
        loop: Any | None = None,
        scheduler: Any | None = None,
    ) -> None:
        self._create_process = create_process
        self._create_task = create_task
        self._gather = gather
        self._emit = emit
        self._spawn = spawn
        self.loop = loop
        self.scheduler = scheduler

    def create_process(self, agent: str, **fields: Any) -> AgentProcessHandle:
        if self._create_process is not None:
            record = self._create_process(agent, **fields)
        else:
            record = {
                "process_id": fields.pop("process_id", None) or _new_id(),
                "agent": agent,
                "state": fields.pop("state", "new"),
                "memory": dict(fields.pop("memory", None) or {}),
                "context": dict(fields.pop("context", None) or {}),
                "parent_id": fields.pop("parent_id", None),
                "children": list(fields.pop("children", None) or ()),
                "threads": list(fields.pop("threads", None) or ()),
                "budget": dict(fields.pop("budget", None) or {}),
            }
            record.update(fields)
        if isinstance(record, AgentProcessHandle):
            return record
        return AgentProcessHandle(
            dict(record),
            create_task=self._bound_create_task,
            spawn=self._spawn,
        )

    def create_task(self, **fields: Any) -> Any:
        return self._bound_create_task(**fields)

    def _bound_create_task(self, **fields: Any) -> Any:
        if self._create_task is None:
            raise RuntimeError("Host must inject create_task")
        return self._create_task(**fields)

    async def gather(self, *tasks: Any) -> Any:
        if self._gather is None:
            raise RuntimeError("Host must inject gather")
        return await _call(self._gather, *tasks)

    async def emit(self, record: Mapping[str, Any]) -> Any:
        if self._emit is not None:
            return await _call(self._emit, record)
        loop = self.loop
        if loop is not None:
            emit = getattr(loop, "emit", None)
            if callable(emit):
                return await _call(emit, record)
        raise RuntimeError("Host must inject emit or loop")

    async def run_until_idle(self, **kwargs: Any) -> Any:
        loop = self.loop
        if loop is None:
            raise RuntimeError("Host must inject loop")
        runner = getattr(loop, "run_until_idle", None)
        if not callable(runner):
            raise TypeError("loop must provide run_until_idle")
        return await _call(runner, **kwargs)

    async def run(self) -> Any:
        loop = self.loop
        if loop is None:
            raise RuntimeError("Host must inject loop")
        runner = getattr(loop, "run_forever", None)
        if not callable(runner):
            raise TypeError("loop must provide run_forever")
        return await _call(runner)
