"""A fixed-size worker pool for synchronous plugins inside one process."""

from __future__ import annotations

import asyncio
import threading
from queue import SimpleQueue
from typing import Any, Callable


class WorkerPool:
    """Peer workers inside one process with a fixed startup size."""

    def __init__(self, max_workers: int, *, name: str = "linope-sync") -> None:
        if max_workers < 0:
            raise ValueError("工人人数不能是负数")
        self._name = name
        self._max = int(max_workers)
        self._threads: set[threading.Thread] = set()
        self._queue: SimpleQueue[Any] = SimpleQueue()
        self._lock = threading.Lock()
        self._shutdown = False

    @property
    def max_workers(self) -> int:
        return self._max

    async def run(self, function: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        if self._max <= 0 or self._shutdown:
            raise RuntimeError("同步插件线程池已禁用")
        loop = asyncio.get_running_loop()
        future: asyncio.Future[Any] = loop.create_future()
        self._queue.put((function, args, kwargs, loop, future))
        self._adjust()
        return await future

    def shutdown(self, *, wait: bool = True) -> None:
        with self._lock:
            self._shutdown = True
            threads = list(self._threads)
            self._max = 0
        for _thread in threads:
            self._queue.put(None)
        if wait:
            for thread in threads:
                thread.join(timeout=5)

    def _adjust(self) -> None:
        with self._lock:
            if self._shutdown or self._max <= 0:
                return
            alive = {thread for thread in self._threads if thread.is_alive()}
            self._threads = alive
            if len(self._threads) >= self._max:
                return
            thread = threading.Thread(
                target=_worker,
                args=(self,),
                name=f"{self._name}-{len(self._threads)}",
                daemon=True,
            )
            self._threads.add(thread)
            thread.start()


def _worker(pool: WorkerPool) -> None:
    while True:
        item = pool._queue.get()
        if item is None:
            with pool._lock:
                pool._threads.discard(threading.current_thread())
            return
        function, args, kwargs, loop, future = item
        if future.cancelled():
            continue
        try:
            result = function(*args, **kwargs)
        except Exception as error:
            loop.call_soon_threadsafe(future.set_exception, error)
        else:
            loop.call_soon_threadsafe(future.set_result, result)
        with pool._lock:
            if pool._shutdown:
                pool._threads.discard(threading.current_thread())
                return
