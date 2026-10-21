"""The running pool follows a ceiling that was already raised."""

from __future__ import annotations

import asyncio
import threading
import time
from collections import deque
from typing import Any

from kernel.load_balancing.workers import WorkerPool
from kernel.process.ledger import ProcessLedger
from kernel.process.process_runtime.runtime import ceilings_from_ledger
from kernel.thread.contracts import ClaimedRequest, ThreadPolicy
from kernel.thread.runtime import ThreadRuntime


class _Inbox:
    def __init__(self, count: int) -> None:
        self._requests = deque(
            ClaimedRequest(
                request_id=str(index),
                process_id="7",
                body={"number": index},
            )
            for index in range(count)
        )
        self.completed: list[dict[str, Any]] = []
        self._lock = threading.Lock()

    def claim(
        self,
        process_id: str,
        worker_id: str,
        lease_seconds: float,
    ) -> ClaimedRequest | None:
        del process_id, worker_id, lease_seconds
        with self._lock:
            if not self._requests:
                return None
            return self._requests.popleft()

    def complete(
        self,
        request_id: str,
        reply: dict[str, Any],
        claim_token: str | None = None,
    ) -> None:
        with self._lock:
            self.completed.append(
                {
                    "request_id": request_id,
                    "reply": reply,
                    "claim_token": claim_token,
                }
            )

    def lookup(self, request_id: str) -> dict[str, Any] | None:
        del request_id
        return None


class _SyncAdapter:
    is_async = False
    sync_thread_safe = True

    def __init__(self) -> None:
        self.names: list[str] = []
        self.active = 0
        self.maximum = 0
        self._lock = threading.Lock()
        self._gate = threading.Event()

    def handle(self, request: dict[str, Any]) -> dict[str, Any]:
        del request
        with self._lock:
            self.names.append(threading.current_thread().name)
            self.active += 1
            self.maximum = max(self.maximum, self.active)
        self._gate.wait(timeout=1)
        with self._lock:
            self.active -= 1
        return {"ok": True}


class _UnsafeAdapter:
    is_async = False
    sync_thread_safe = False

    def __init__(self) -> None:
        self.active = 0
        self.maximum = 0
        self._lock = threading.Lock()

    def handle(self, request: dict[str, Any]) -> dict[str, Any]:
        del request
        with self._lock:
            self.active += 1
            self.maximum = max(self.maximum, self.active)
        time.sleep(0.05)
        with self._lock:
            self.active -= 1
        return {"ok": True}


def test_worker_ceiling_can_rise_while_the_pool_is_running() -> None:
    pool = WorkerPool(1)
    seen: list[str] = []
    gate = threading.Event()

    def block() -> str:
        seen.append(threading.current_thread().name)
        gate.wait(timeout=1)
        return "ok"

    async def run() -> None:
        pool.add(1)
        first = asyncio.create_task(pool.run(block))
        second = asyncio.create_task(pool.run(block))
        await asyncio.sleep(0.05)
        assert pool.max_workers == 2
        gate.set()
        assert await first == "ok"
        assert await second == "ok"
        pool.shutdown()

    asyncio.run(run())
    assert len(seen) == 2
    assert len(set(seen)) == 2


def test_runtime_follows_a_raised_ceiling() -> None:
    inbox = _Inbox(2)
    adapter = _SyncAdapter()
    seen = {"calls": 0}

    def ceilings() -> tuple[int, int]:
        seen["calls"] += 1
        if seen["calls"] < 2:
            return (1, 1)
        return (2, 2)

    async def stop() -> bool:
        if len(adapter.names) >= 2:
            adapter._gate.set()
        return len(inbox.completed) == 2

    async def run() -> None:
        await ThreadRuntime(
            ThreadPolicy(
                max_concurrent_tasks=1,
                max_sync_workers=1,
                poll_interval_seconds=0,
            )
        ).run(
            process_id="7",
            inbox=inbox,
            adapter=adapter,
            should_stop=stop,
            ceilings=ceilings,
        )

    asyncio.run(asyncio.wait_for(run(), timeout=2))
    assert len(inbox.completed) == 2
    assert adapter.maximum == 2
    assert len(set(adapter.names)) == 2


def test_an_unsafe_plugin_stays_on_one_worker() -> None:
    inbox = _Inbox(2)
    adapter = _UnsafeAdapter()

    async def stop() -> bool:
        return len(inbox.completed) == 2

    async def run() -> None:
        await ThreadRuntime(
            ThreadPolicy(
                max_concurrent_tasks=1,
                max_sync_workers=1,
                poll_interval_seconds=0,
            )
        ).run(
            process_id="7",
            inbox=inbox,
            adapter=adapter,
            should_stop=stop,
            ceilings=lambda: (5, 5),
        )

    asyncio.run(asyncio.wait_for(run(), timeout=2))
    assert adapter.maximum == 1


def test_ledger_row_supplies_the_ceilings(tmp_path) -> None:
    path = tmp_path / "processes.json"
    ProcessLedger(path).write(
        [
            {
                "capability_id": "demo",
                "status": "ready",
                "claims": [],
                "leases": [],
                "room": {
                    "mode": "workspace-write",
                    "channel": "",
                    "worker_ceiling": 2,
                    "inflight_ceiling": 3,
                },
                "pid": 7,
                "started": "boot",
            }
        ]
    )
    assert ceilings_from_ledger(str(path), 7, (1, 1)) == (2, 3)
