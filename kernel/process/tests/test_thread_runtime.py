from __future__ import annotations

import asyncio
import threading
import time
from collections import deque
from typing import Any

from kernel.process.ledger import MemoryResourceStore
from kernel.process.ledger import FileResourceStore
from kernel.thread.contracts import ClaimedRequest, ThreadPolicy
from kernel.thread.runtime import ThreadRuntime


def test_memory_store_claims_one_pending_request_once() -> None:
    store = MemoryResourceStore()
    first = store.submit_request("process", {"number": 1})
    claimed = store.claim_request("process", "worker-a", 30)

    assert claimed is not None
    assert claimed["request_id"] == first
    assert claimed["claim_token"]
    assert store.claim_request("process", "worker-b", 30) is None

    store.complete_request(first, {"event": "result"}, claimed["claim_token"])
    assert store.lookup_request(first)["status"] == "done"


def test_expired_claim_can_be_requeued_but_old_token_cannot_complete() -> None:
    store = MemoryResourceStore()
    request_id = store.submit_request("process", {"number": 1})
    first = store.claim_request("process", "worker-a", 0.01)
    assert first is not None
    time.sleep(0.02)

    second = store.claim_request("process", "worker-b", 30)
    assert second is not None
    assert second["claim_token"] != first["claim_token"]

    store.complete_request(request_id, {"result": "stale"}, first["claim_token"])
    assert store.lookup_request(request_id)["status"] == "claimed"
    store.complete_request(request_id, {"result": "fresh"}, second["claim_token"])
    assert store.lookup_request(request_id)["reply"] == {"result": "fresh"}


def test_file_store_persists_claim_state(tmp_path) -> None:
    path = tmp_path / "resources.json"
    store = FileResourceStore(path)
    request_id = store.submit_request("process", {"number": 1})
    claim = store.claim_request("process", "worker", 30)
    assert claim is not None
    store.close()

    reopened = FileResourceStore(path)
    try:
        assert reopened.lookup_request(request_id)["status"] == "claimed"
        reopened.complete_request(request_id, {"event": "done"}, claim["claim_token"])
        assert reopened.lookup_request(request_id)["status"] == "done"
    finally:
        reopened.close()


class _Inbox:
    def __init__(self, count: int) -> None:
        self._requests = deque(
            ClaimedRequest(
                request_id=str(index),
                process_id="process",
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


class _AsyncAdapter:
    is_async = True

    async def handle_async(self, request: dict[str, Any]) -> dict[str, Any]:
        await asyncio.sleep(0.01)
        return {"number": request["number"]}


class _SyncAdapter:
    is_async = False
    sync_thread_safe = True

    def __init__(self) -> None:
        self.active = 0
        self.maximum = 0
        self._lock = threading.Lock()

    def handle(self, request: dict[str, Any]) -> dict[str, Any]:
        del request
        with self._lock:
            self.active += 1
            self.maximum = max(self.maximum, self.active)
        time.sleep(0.02)
        with self._lock:
            self.active -= 1
        return {"ok": True}


def test_async_runtime_limits_async_requests_without_sync_workers() -> None:
    inbox = _Inbox(6)
    completed = asyncio.Event()

    async def stop() -> bool:
        if len(inbox.completed) == 6:
            completed.set()
        return completed.is_set()

    async def run() -> None:
        await ThreadRuntime(
            ThreadPolicy(
                max_concurrent_tasks=3,
                max_sync_workers=0,
                poll_interval_seconds=0,
            )
        ).run(
            process_id="process",
            inbox=inbox,
            adapter=_AsyncAdapter(),
            should_stop=stop,
        )

    asyncio.run(asyncio.wait_for(run(), timeout=2))
    assert len(inbox.completed) == 6
    assert all(item["reply"]["event"] == "result" for item in inbox.completed)


def test_sync_plugins_use_bounded_thread_pool() -> None:
    inbox = _Inbox(5)
    adapter = _SyncAdapter()

    async def stop() -> bool:
        return len(inbox.completed) == 5

    async def run() -> None:
        await ThreadRuntime(
            ThreadPolicy(
                max_concurrent_tasks=5,
                max_sync_workers=2,
                poll_interval_seconds=0,
            )
        ).run(
            process_id="process",
            inbox=inbox,
            adapter=adapter,
            should_stop=stop,
        )

    asyncio.run(asyncio.wait_for(run(), timeout=2))
    assert len(inbox.completed) == 5
    assert adapter.maximum <= 2
