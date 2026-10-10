"""Async-first execution runtime for one capability process."""

from __future__ import annotations

import asyncio
import inspect
import os
import time
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from kernel.load_balancing.inflight import InflightLimit
from kernel.load_balancing.workers import WorkerPool
from kernel.thread.contracts import ClaimedRequest, ThreadInbox, ThreadPolicy
from kernel.thread.limiter import AsyncTaskLimiter


class ThreadRuntime:
    """Schedule async handlers and bridge blocking handlers to a thread pool."""

    def __init__(self, policy: ThreadPolicy) -> None:
        self.policy = policy
        self._workers: WorkerPool | None = None
        self._task_limiter = AsyncTaskLimiter(policy.max_concurrent_tasks)
        self._session_locks: dict[str, asyncio.Lock] = {}
        self._wait_for_sync_shutdown = True
        self._inflight: InflightLimit | None = None
        self._active = 0

    async def run(
        self,
        *,
        process_id: str,
        inbox: ThreadInbox,
        adapter: Any | None,
        should_stop: Callable[[], bool | Awaitable[bool]],
        staff_ceiling: Callable[[], int | None] | None = None,
        inflight_ceiling: Callable[[], int | None] | None = None,
    ) -> None:
        """Run until the process asks for a cooperative stop."""

        pending: set[asyncio.Task[None]] = set()
        self._wait_for_sync_shutdown = True
        self._thread_safe = bool(getattr(adapter, "sync_thread_safe", False))
        self._workers = WorkerPool(self._sync_worker_count(adapter))
        if _adapter_is_async(adapter):
            self._inflight = InflightLimit(
                minimum=self.policy.min_concurrent_tasks,
                maximum=self.policy.max_concurrent_tasks,
            )
        try:
            stopping = False
            while not stopping:
                if await _resolve(should_stop):
                    stopping = True
                    break

                self._apply_ceilings(staff_ceiling, inflight_ceiling)
                self._discard_finished(pending)
                if len(pending) >= self._admit_limit():
                    await self._wait_for_one(pending)
                    continue

                request = await asyncio.to_thread(
                    inbox.claim,
                    process_id,
                    f"async-runtime-{uuid.uuid4().hex}",
                    self.policy.claim_lease_seconds,
                )
                if request is None:
                    await asyncio.sleep(self.policy.poll_interval_seconds)
                    continue

                task = asyncio.create_task(
                    self._execute_request(inbox, adapter, request),
                    name=f"linope-request-{request.request_id}",
                )
                pending.add(task)

            await self._drain(pending)
        finally:
            if self._workers is not None:
                self._workers.shutdown(wait=self._wait_for_sync_shutdown)
                self._workers = None

    async def _execute_request(
        self,
        inbox: ThreadInbox,
        adapter: Any | None,
        request: ClaimedRequest,
    ) -> None:
        async with self._task_limiter.slot():
            self._active += 1
            started = time.monotonic()
            try:
                lock = self._session_lock(request.body)
                if lock is None:
                    reply = await self._dispatch(adapter, request.body)
                else:
                    async with lock:
                        reply = await self._dispatch(adapter, request.body)
                if self._inflight is not None:
                    self._inflight.sample(time.monotonic() - started, self._active)
            finally:
                self._active -= 1
            reply["request_id"] = request.request_id
            await asyncio.to_thread(
                inbox.complete,
                request.request_id,
                reply,
                request.claim_token,
            )

    async def _dispatch(
        self,
        adapter: Any | None,
        message: dict[str, Any],
    ) -> dict[str, Any]:
        operation = message.get("operation")
        if operation == "ping":
            return {"event": "pong", "pid": os.getpid()}
        if adapter is None or not (
            hasattr(adapter, "handle") or hasattr(adapter, "handle_async")
        ):
            return {
                "event": "error",
                "error": f"No adapter is registered for {operation!r}",
            }

        payload = {
            key: value for key, value in message.items() if key != "request_id"
        }
        try:
            if _adapter_is_async(adapter):
                handler = getattr(adapter, "handle_async", None)
                if handler is None:
                    handler = adapter.handle
                result = handler(payload)
                if inspect.isawaitable(result):
                    result = await result
            else:
                if self._workers is None:
                    raise RuntimeError("同步插件执行器尚未启动")
                result = await self._workers.run(adapter.handle, payload)
        except Exception as error:
            return {
                "event": "error",
                "error_type": type(error).__name__,
                "error": str(error),
            }
        return {"event": "result", "result": result}

    def _sync_worker_count(self, adapter: Any | None) -> int:
        if adapter is None or _adapter_is_async(adapter):
            return 0
        if getattr(adapter, "sync_thread_safe", False):
            return self.policy.max_sync_workers
        return min(1, self.policy.max_sync_workers)

    def _admit_limit(self) -> int:
        if self._inflight is None:
            return self.policy.max_concurrent_tasks
        return self._inflight.current

    def _apply_ceilings(
        self,
        staff_ceiling: Callable[[], int | None] | None,
        inflight_ceiling: Callable[[], int | None] | None,
    ) -> None:
        if staff_ceiling is not None and self._workers is not None:
            ceiling = staff_ceiling()
            if ceiling is not None:
                allowed = ceiling if self._thread_safe else min(1, ceiling)
                if self._workers.max_workers != allowed:
                    self._workers.set_max_workers(allowed)
        if inflight_ceiling is not None and self._inflight is not None:
            ceiling = inflight_ceiling()
            if ceiling is not None and ceiling != self._inflight.maximum:
                self._inflight.set_maximum(ceiling)
                self._task_limiter.expand_to(ceiling)

    def _session_lock(self, body: dict[str, Any]) -> asyncio.Lock | None:
        if not self.policy.session_affinity:
            return None
        session_id = body.get("session_id")
        if session_id in (None, ""):
            return None
        key = str(session_id)
        lock = self._session_locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            self._session_locks[key] = lock
        return lock

    @staticmethod
    def _discard_finished(pending: set[asyncio.Task[None]]) -> None:
        for task in tuple(pending):
            if task.done():
                pending.remove(task)
                task.result()

    @staticmethod
    async def _wait_for_one(pending: set[asyncio.Task[None]]) -> None:
        if not pending:
            return
        done, _ = await asyncio.wait(
            pending,
            return_when=asyncio.FIRST_COMPLETED,
        )
        pending.difference_update(done)
        for task in done:
            task.result()

    async def _drain(self, pending: set[asyncio.Task[None]]) -> None:
        if not pending:
            return
        done, remaining = await asyncio.wait(
            pending,
            timeout=self.policy.shutdown_timeout_seconds,
        )
        for task in done:
            task.result()
        for task in remaining:
            task.cancel()
        if remaining:
            self._wait_for_sync_shutdown = False
            await asyncio.gather(*remaining, return_exceptions=True)


def _adapter_is_async(adapter: Any) -> bool:
    explicit = getattr(adapter, "is_async", None)
    if explicit is not None:
        return bool(explicit)
    return inspect.iscoroutinefunction(getattr(adapter, "handle_async", None))


async def _resolve(value: Callable[[], bool | Awaitable[bool]]) -> bool:
    result = value()
    return bool(await result) if inspect.isawaitable(result) else bool(result)
