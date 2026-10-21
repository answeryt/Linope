"""A worker pool whose ceiling can change while it is running."""

from __future__ import annotations

import asyncio
import threading
from queue import SimpleQueue
from typing import Any, Callable


class WorkerPool:
    """Peer workers inside one process. The ceiling is not frozen at creation."""

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

    def set_max_workers(self, count: int) -> int:
        if count < 0:
            raise ValueError("工人人数不能是负数")
        with self._lock:
            self._max = int(count)
        self._adjust()
        return self._max

    def add(self, count: int = 1) -> int:
        return self.set_max_workers(self._max + int(count))

    def remove(self, count: int = 1) -> int:
        return self.set_max_workers(max(0, self._max - int(count)))

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


def raise_ceiling(store: Any, capability: str, count: int = 1) -> int:
    """Raise the live ceiling written on each running process of this capability."""
    return _move_ceiling(store, capability, int(count))


def lower_ceiling(store: Any, capability: str, count: int = 1) -> int:
    """Lower the live ceiling, never under one."""
    return _move_ceiling(store, capability, -int(count))


def raise_on_process(store: Any, process_id: str, count: int, ceiling: int) -> int:
    """Raise one process by ``count``, stopping at ``ceiling``."""
    row = store.get_process(process_id)
    if row is None:
        raise KeyError(process_id)
    current = _current_worker_ceiling(row)
    updated = min(int(ceiling), current + int(count))
    store.set_worker_ceiling(process_id, updated)
    return updated


def _move_ceiling(store: Any, capability: str, delta: int) -> int:
    rows = store.running_processes(capability)
    if not rows:
        raise ValueError("这个能力还没有在跑的进程")
    ready = rows[0].get("ready") if isinstance(rows[0].get("ready"), dict) else {}
    if ready.get("is_async"):
        current = _current_inflight_ceiling(rows[0])
        updated = max(1, current + delta)
        for row in rows:
            store.set_inflight_ceiling(row["process_id"], updated)
        return updated
    if ready and not ready.get("sync_thread_safe"):
        raise ValueError("这个进程不能几个人一起改，请再开一个进程")
    current = _current_worker_ceiling(rows[0])
    updated = max(1, current + delta)
    for row in rows:
        store.set_worker_ceiling(row["process_id"], updated)
    return updated


def _current_worker_ceiling(row: dict[str, Any]) -> int:
    if row.get("worker_ceiling") is not None:
        return int(row["worker_ceiling"])
    policy = _policy(row)
    return int(policy.get("max_sync_workers", 1))


def _current_inflight_ceiling(row: dict[str, Any]) -> int:
    if row.get("inflight_ceiling") is not None:
        return int(row["inflight_ceiling"])
    policy = _policy(row)
    return int(policy.get("max_concurrent_tasks", 1))


def _policy(row: dict[str, Any]) -> dict[str, Any]:
    activation = row.get("activation")
    if not isinstance(activation, dict):
        return {}
    policy = activation.get("thread_policy")
    if not isinstance(policy, dict):
        return {}
    return policy


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
            extra = pool._max > 0 and len(pool._threads) > pool._max
            if pool._shutdown or extra:
                pool._threads.discard(threading.current_thread())
                return
