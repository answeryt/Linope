"""Async-first execution runtime for one capability process."""

from __future__ import annotations

import asyncio
import contextvars
import inspect
import os
from collections.abc import Awaitable, Callable
from typing import Any

from kernel.load_balancing.workers import WorkerPool
from kernel.thread.contracts import ClaimedRequest, ThreadInbox, ThreadPolicy
from kernel.thread.limiter import AsyncTaskLimiter


Ceilings = Callable[[], tuple[int, int]]


class ThreadRuntime:
    """Schedule async handlers and bridge blocking handlers to a thread pool."""

    def __init__(self, policy: ThreadPolicy) -> None:
        self.policy = policy
        self._workers: WorkerPool | None = None
        self._task_limiter = AsyncTaskLimiter(policy.max_concurrent_tasks)
        self._session_locks: dict[str, asyncio.Lock] = {}
        self._wait_for_sync_shutdown = True
        self._process_id = ""
        self._ceilings: Ceilings | None = None

    async def run(
        self,
        *,
        process_id: str,
        inbox: ThreadInbox,
        adapter: Any | None,
        should_stop: Callable[[], bool | Awaitable[bool]],
        ceilings: Ceilings | None = None,
    ) -> None:
        """Run until the process asks for a cooperative stop."""

        from kernel.scheduler.threads import run_runtime

        await run_runtime(
            self,
            process_id=process_id,
            inbox=inbox,
            adapter=adapter,
            should_stop=should_stop,
            ceilings=ceilings,
        )

    async def _execute_request(
        self,
        inbox: ThreadInbox,
        adapter: Any | None,
        request: ClaimedRequest,
    ) -> None:
        async with self._task_limiter.slot():
            try:
                lock = self._session_lock(request.body)
                if lock is None:
                    reply = await self._dispatch(adapter, request.body)
                else:
                    async with lock:
                        reply = await self._dispatch(adapter, request.body)
            except Exception as error:
                reply = {
                    "event": "error",
                    "error_type": type(error).__name__,
                    "error": str(error),
                }
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
            pid = self._reply_pid()
            if "pid" in message and int(message.get("pid") or 0) != pid:
                return {"event": "error", "error": "This is not this capability's pid"}
            return {
                "event": "pong",
                "pid": pid,
                "seq": message.get("seq"),
                "channel": str(message.get("channel") or ""),
            }
        if adapter is None or not (
            hasattr(adapter, "handle") or hasattr(adapter, "handle_async")
        ):
            return {"event": "error", "error": "This process has no load"}

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
                    raise RuntimeError("The synchronous plugin executor has not started")
                context = contextvars.copy_context()
                result = await self._workers.run(context.run, adapter.handle, payload)
        except Exception as error:
            return {
                "event": "error",
                "error_type": type(error).__name__,
                "error": str(error),
            }
        return {"event": "result", "result": result}

    def _align(self, adapter: Any | None) -> None:
        """Apply the ledger ceilings with the pool and limiter that already exist."""
        if self._ceilings is None or self._workers is None:
            return
        worker, inflight = self._ceilings()
        inflight = int(inflight)
        if inflight >= 1:
            self._task_limiter.expand_to(inflight)
        allowed = self._worker_cap(adapter, int(worker))
        if allowed != self._workers.max_workers:
            self._workers.set_max_workers(allowed)

    def _sync_worker_count(self, adapter: Any | None) -> int:
        return self._worker_cap(adapter, self.policy.max_sync_workers)

    def _worker_cap(self, adapter: Any | None, requested: int) -> int:
        if adapter is None or _adapter_is_async(adapter):
            return 0
        if getattr(adapter, "sync_thread_safe", False):
            return max(0, int(requested))
        return min(1, max(0, int(requested)))

    def _admit_limit(self) -> int:
        return self._task_limiter.capacity

    def _reply_pid(self) -> int:
        try:
            pid = int(self._process_id)
        except (TypeError, ValueError):
            pid = 0
        return pid if pid > 0 else os.getpid()

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
