"""Admit work onto one process runtime. The runtime still executes each request."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from kernel.load_balancing.workers import WorkerPool
from kernel.thread.runtime import _resolve


async def run_runtime(
    runtime: Any,
    *,
    process_id: str,
    inbox: Any,
    adapter: Any | None,
    should_stop: Callable[[], bool | Awaitable[bool]],
    ceilings: Callable[[], tuple[int, int]] | None = None,
) -> None:
    """Claim and admit requests until the process asks to stop."""

    pending: set[asyncio.Task[None]] = set()
    runtime._wait_for_sync_shutdown = True
    runtime._process_id = str(process_id)
    runtime._ceilings = ceilings
    runtime._workers = WorkerPool(runtime._sync_worker_count(adapter))
    claimed_once = False
    try:
        stopping = False
        while not stopping:
            if await _resolve(should_stop):
                stopping = True
                break

            runtime._discard_finished(pending)
            if claimed_once:
                runtime._align(adapter)
            if len(pending) >= runtime._admit_limit():
                await runtime._wait_for_one(pending)
                continue

            request = await asyncio.to_thread(
                inbox.claim,
                process_id,
                f"async-runtime-{uuid.uuid4().hex}",
                runtime.policy.claim_lease_seconds,
            )
            if request is None:
                if await _resolve(should_stop):
                    stopping = True
                    break
                await asyncio.sleep(runtime.policy.poll_interval_seconds)
                continue

            claimed_once = True
            runtime._align(adapter)
            task = asyncio.create_task(
                runtime._execute_request(inbox, adapter, request),
                name=f"linope-request-{request.request_id}",
            )
            pending.add(task)

        await runtime._drain(pending)
    finally:
        if runtime._workers is not None:
            runtime._workers.shutdown(wait=runtime._wait_for_sync_shutdown)
            runtime._workers = None
