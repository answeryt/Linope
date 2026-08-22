# -*- coding: utf-8 -*-
"""Structured gather for Agent Tasks.

On the first failure, remaining tasks are cancelled. Host injects this
callable into the runtime. Do not import the task plugin.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterable
from typing import Any


PLUGIN_NAME = "kernel_async_gather"
PLUGIN_VERSION = "1.0"


async def _coerce(item: Any) -> Any:
    if asyncio.isfuture(item) or asyncio.iscoroutine(item):
        return await item
    if callable(getattr(item, "__await__", None)):
        return await item
    return item


async def gather_tasks(
    *items: Any,
    return_exceptions: bool = False,
) -> list[Any]:
    """Wait for all items. Cancel siblings if one raises and return_exceptions is false."""
    if len(items) == 1 and isinstance(items[0], Iterable) and not callable(
        getattr(items[0], "__await__", None)
    ) and not asyncio.iscoroutine(items[0]) and not asyncio.isfuture(items[0]):
        pending = list(items[0])
    else:
        pending = list(items)
    tasks = [asyncio.ensure_future(_coerce(item)) for item in pending]
    if not tasks:
        return []
    try:
        return list(await asyncio.gather(*tasks, return_exceptions=return_exceptions))
    except BaseException:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        raise
