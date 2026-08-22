# -*- coding: utf-8 -*-
"""In-process event bus: queue plus optional observer callbacks.

The event loop is the consumer of get(). subscribe handlers observe copies
and must not drain the queue. Host injects this bus into the loop.
"""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Callable, Mapping
from typing import Any


PLUGIN_NAME = "kernel_async_event_bus"
PLUGIN_VERSION = "1.0"


async def _call(func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    result = func(*args, **kwargs)
    if inspect.isawaitable(result):
        return await result
    return result


class EventBus:
    """asyncio.Queue wrapper with fire-and-forget observers."""

    def __init__(self, *, maxsize: int = 0) -> None:
        self._queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=maxsize)
        self._observers: list[Callable[..., Any]] = []

    def subscribe(self, handler: Callable[..., Any]) -> Callable[..., Any]:
        self._observers.append(handler)
        return handler

    async def publish(self, record: Mapping[str, Any]) -> dict[str, Any]:
        payload = dict(record)
        await self._queue.put(payload)
        for handler in list(self._observers):
            await _call(handler, payload)
        return payload

    async def get(self) -> dict[str, Any]:
        return await self._queue.get()

    def get_nowait(self) -> dict[str, Any]:
        return self._queue.get_nowait()

    def empty(self) -> bool:
        return self._queue.empty()

    def qsize(self) -> int:
        return self._queue.qsize()

    def task_done(self) -> None:
        self._queue.task_done()
