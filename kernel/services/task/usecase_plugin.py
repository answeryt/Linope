# -*- coding: utf-8 -*-
"""Run one agent task through middlewares, then the injected agent loop.

This is the FastStream process_message slot: one queue item becomes one
loop session. Middlewares, loop, emit, and model/tool handlers are injected.
"""

from __future__ import annotations

import inspect
import logging
from collections.abc import Callable, Mapping, Sequence
from contextlib import AsyncExitStack
from typing import Any, Awaitable


PLUGIN_NAME = "kernel_task_usecase"
PLUGIN_VERSION = "1.0"

AgentLoop = Callable[..., Any | Awaitable[Any]]


class AgentTaskInvalid(ValueError):
    """Task payload cannot be processed."""


async def _call(func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    result = func(*args, **kwargs)
    if inspect.isawaitable(result):
        return await result
    return result


def _wrap(middleware: Any, call_next: Callable[[Mapping[str, Any]], Awaitable[Any]]) -> Callable[[Mapping[str, Any]], Awaitable[Any]]:
    consume = getattr(middleware, "consume_scope", None)
    if not callable(consume):
        return call_next

    async def wrapped(task: Mapping[str, Any]) -> Any:
        return await consume(call_next, task)

    return wrapped


class AgentTaskUsecase:
    """Consume one task mapping and run the agent loop inside it."""

    def __init__(
        self,
        *,
        agent_loop: AgentLoop,
        middlewares: Sequence[Any] = (),
        emit: Callable[..., Any] | None = None,
        call_model: Callable[..., Any] | None = None,
        call_tool: Callable[..., Any] | None = None,
        context_repo: Any | None = None,
        max_turns: int = 16,
        logger: logging.Logger | None = None,
    ) -> None:
        if agent_loop is None:
            raise TypeError("agent_loop is required")
        self.agent_loop = agent_loop
        self.middlewares = list(middlewares)
        self.emit = emit
        self.call_model = call_model
        self.call_tool = call_tool
        self.context_repo = context_repo
        self.max_turns = max_turns
        self.logger = logger or logging.getLogger(PLUGIN_NAME)
        self.in_flight = 0
        self.running = True

    async def process_task(self, task: Mapping[str, Any]) -> Any:
        if not self.running:
            return None
        if not isinstance(task, Mapping) or "user_message" not in task:
            raise AgentTaskInvalid("task must be a mapping with user_message")

        self.in_flight += 1
        try:
            async with AsyncExitStack() as stack:
                repo = self.context_repo
                if repo is not None and hasattr(repo, "scope"):
                    stack.enter_context(repo.scope("task", task))
                    stack.enter_context(repo.scope("task_id", task.get("task_id")))

                call = self._run_loop
                for middleware in reversed(self.middlewares):
                    call = _wrap(middleware, call)
                return await call(task)
        finally:
            self.in_flight = max(0, self.in_flight - 1)

    async def _run_loop(self, task: Mapping[str, Any]) -> Any:
        return await _call(
            self.agent_loop,
            task,
            call_model=self.call_model,
            call_tool=self.call_tool,
            emit=self.emit,
            max_turns=self.max_turns,
        )

    async def stop(self) -> None:
        self.running = False
