"""Async capacity limits for process-local work."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator


class AsyncTaskLimiter:
    """Bound the number of requests admitted to one capability process."""

    def __init__(self, capacity: int) -> None:
        if capacity < 1:
            raise ValueError("capacity must be at least 1")
        self.capacity = capacity
        self._semaphore = asyncio.Semaphore(capacity)

    @asynccontextmanager
    async def slot(self) -> AsyncIterator[None]:
        await self._semaphore.acquire()
        try:
            yield
        finally:
            self._semaphore.release()

    def expand_to(self, capacity: int) -> None:
        """Raise the admission cap. A lower number waits for the caller to admit fewer."""
        capacity = int(capacity)
        if capacity < 1:
            raise ValueError("capacity must be at least 1")
        extra = capacity - self.capacity
        if extra <= 0:
            return
        for _ in range(extra):
            self._semaphore.release()
        self.capacity = capacity

    @property
    def available(self) -> int:
        return max(0, int(self._semaphore._value))
