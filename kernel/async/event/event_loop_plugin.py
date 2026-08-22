# -*- coding: utf-8 -*-
"""Drive Agent Executions from events instead of a while-loop.

bus is required. dispatch / scheduler are injected. A ``_stop`` event
ends run_forever. Host must not split one agent session into many queue
messages; events here are in-process.
"""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Callable, Mapping
from typing import Any


PLUGIN_NAME = "kernel_async_event_loop"
PLUGIN_VERSION = "1.0"

STOP = "_stop"

Dispatch = Callable[..., Any]


async def _call(func: Callable[..., Any] | None, *args: Any, **kwargs: Any) -> Any:
    if func is None:
        return None
    result = func(*args, **kwargs)
    if inspect.isawaitable(result):
        return await result
    return result


class AgentEventLoop:
    """Pull one event and dispatch it. Scheduler is held for the Host."""

    def __init__(
        self,
        bus: Any,
        *,
        dispatch: Dispatch | None = None,
        scheduler: Any | None = None,
        executions: Any | None = None,
    ) -> None:
        if bus is None:
            raise TypeError("bus is required")
        self.bus = bus
        self.dispatch = dispatch
        self.scheduler = scheduler
        self.executions = executions
        self._stopped = False
        self.in_flight = 0

    async def emit(self, record: Mapping[str, Any]) -> Any:
        publish = getattr(self.bus, "publish", None)
        if not callable(publish):
            raise TypeError("bus must provide publish")
        return await _call(publish, record)

    def stop(self) -> None:
        self._stopped = True

    async def request_stop(self) -> None:
        self._stopped = True
        await self.emit({"type": STOP})

    async def step(self) -> bool:
        """Process one queued event. Return False when idle."""
        event = self._get_nowait()
        if event is None:
            return False
        await self._handle(event)
        return True

    async def run_until_idle(self, *, max_steps: int = 10000) -> None:
        for _ in range(max(1, max_steps)):
            if not await self.step():
                return

    async def run_forever(self) -> None:
        self._stopped = False
        getter = getattr(self.bus, "get", None)
        if not callable(getter):
            raise TypeError("bus must provide get")
        while not self._stopped:
            event = await _call(getter)
            if event.get("type") == STOP:
                self._stopped = True
                done = getattr(self.bus, "task_done", None)
                if callable(done):
                    done()
                return
            await self._handle(event)

    async def _handle(self, event: Mapping[str, Any]) -> None:
        payload = dict(event)
        self.in_flight += 1
        try:
            await _call(self.dispatch, payload, loop=self)
        finally:
            self.in_flight = max(0, self.in_flight - 1)
            done = getattr(self.bus, "task_done", None)
            if callable(done):
                done()

    def _get_nowait(self) -> dict[str, Any] | None:
        getter = getattr(self.bus, "get_nowait", None)
        if callable(getter):
            try:
                return dict(getter())
            except asyncio.QueueEmpty:
                return None
        empty = getattr(self.bus, "empty", None)
        if callable(empty) and empty():
            return None
        return None
