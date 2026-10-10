"""Thread-pool bridge for synchronous capability plugins."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import Any, Callable, TypeVar

T = TypeVar("T")


class SyncExecutor:
    """A bounded executor used only for blocking synchronous handlers."""

    def __init__(self, max_workers: int, *, name: str = "linope-sync") -> None:
        self.max_workers = int(max_workers)
        self._executor = (
            ThreadPoolExecutor(
                max_workers=self.max_workers,
                thread_name_prefix=name,
            )
            if self.max_workers > 0
            else None
        )

    async def run(self, function: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        if self._executor is None:
            raise RuntimeError("同步插件线程池已禁用")
        loop = asyncio.get_running_loop()
        call = partial(function, *args, **kwargs)
        return await loop.run_in_executor(self._executor, call)

    def shutdown(self, *, wait: bool = True) -> None:
        if self._executor is not None:
            self._executor.shutdown(wait=wait)
            self._executor = None
