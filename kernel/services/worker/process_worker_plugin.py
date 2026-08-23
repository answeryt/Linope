# -*- coding: utf-8 -*-
"""Worker that executes leased run-queue items through an injected runtime."""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Callable
from typing import Any


PLUGIN_NAME = "kernel_process_worker"
PLUGIN_VERSION = "1.0"


async def _call(function: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    result = function(*args, **kwargs)
    if inspect.isawaitable(result):
        return await result
    return result


class ProcessWorker:
    """Claim, execute, and settle queue items until stopped."""

    def __init__(
        self,
        *,
        queue: Any,
        runtime: Any,
        worker_id: str,
        lease_seconds: float = 30,
        retry_delay_seconds: float = 0,
        idle_sleep: float = 0.1,
    ) -> None:
        if queue is None or runtime is None:
            raise TypeError("queue and runtime are required")
        if not worker_id:
            raise ValueError("worker_id is required")
        if lease_seconds <= 0:
            raise ValueError("lease_seconds must be positive")
        if retry_delay_seconds < 0 or idle_sleep < 0:
            raise ValueError("retry_delay_seconds and idle_sleep cannot be negative")
        self.queue = queue
        self.runtime = runtime
        self.worker_id = str(worker_id)
        self.lease_seconds = float(lease_seconds)
        self.retry_delay_seconds = float(retry_delay_seconds)
        self.idle_sleep = float(idle_sleep)
        self._stop_event = asyncio.Event()
        self._running = False

    async def run_once(self) -> bool:
        """Execute one available item, returning whether an item was claimed."""
        execute_item = getattr(self.runtime, "execute_queue_item", None)
        claim_kind = None if callable(execute_item) else "process"
        item = await _call(
            self.queue.claim,
            self.worker_id,
            lease_seconds=self.lease_seconds,
            kind=claim_kind,
        )
        if item is None:
            return False

        item_id = str(item["item_id"])
        fencing_token = int(item["fencing_token"])
        try:
            if callable(execute_item):
                await _call(execute_item, item)
            else:
                await _call(self.runtime.run_next, str(item["target_id"]))
        except Exception as exc:
            await _call(
                self.queue.retry,
                item_id,
                self.worker_id,
                fencing_token,
                delay_seconds=self.retry_delay_seconds,
                error=str(exc),
            )
            return True

        await _call(self.queue.ack, item_id, self.worker_id, fencing_token)
        return True

    async def run(self) -> None:
        """Run until ``stop`` is called or this task is cancelled."""
        if self._running:
            raise RuntimeError("worker is already running")
        self._running = True
        self._stop_event.clear()
        try:
            while not self._stop_event.is_set():
                worked = await self.run_once()
                if not worked:
                    await self._wait_until_stopped()
        finally:
            self._running = False

    def stop(self) -> None:
        """Request a running worker to stop."""
        self._stop_event.set()

    async def _wait_until_stopped(self) -> None:
        if self.idle_sleep == 0:
            await asyncio.sleep(0)
            return
        try:
            await asyncio.wait_for(self._stop_event.wait(), timeout=self.idle_sleep)
        except TimeoutError:
            pass

    @property
    def running(self) -> bool:
        return self._running
