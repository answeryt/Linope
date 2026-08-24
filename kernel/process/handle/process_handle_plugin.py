# -*- coding: utf-8 -*-
"""Durable references to Process runs."""

from __future__ import annotations

import asyncio
from copy import deepcopy
from time import monotonic
from typing import Any, Mapping


PLUGIN_NAME = "kernel_process_handle"
PLUGIN_VERSION = "1.0"

_TERMINAL = frozenset({"terminated", "completed", "failed", "cancelled"})


class ProcessFailedError(RuntimeError):
    """Raised when reading the result of a failed durable Process."""

    def __init__(self, process_id: str, error: Any) -> None:
        self.process_id = str(process_id)
        self.error = deepcopy(error)
        if isinstance(error, Mapping):
            message = str(error.get("message") or error.get("type") or "process failed")
        else:
            message = str(error or "process failed")
        super().__init__(message)


class ProcessHandle:
    """A serializable identity plus injected local access dependencies."""

    def __init__(
        self,
        process_id: str,
        run_id: str,
        *,
        store: Any,
        engine: Any,
    ) -> None:
        if store is None or engine is None:
            raise TypeError("store and engine are required")
        self.process_id = str(process_id)
        self.run_id = str(run_id)
        self.store = store
        self.engine = engine

    def status(self) -> dict[str, Any]:
        require_run = getattr(self.store, "require_run", None)
        if callable(require_run):
            record = require_run(self.process_id, self.run_id)
        else:
            require = getattr(self.store, "require", None)
            record = (
                require(self.process_id)
                if callable(require)
                else self.store.get(self.process_id)
            )
        if record is None:
            raise KeyError(self.process_id)
        snapshot = dict(record)
        if str(snapshot.get("run_id")) != self.run_id:
            raise RuntimeError("handle run_id does not match stored Process run")
        return deepcopy(snapshot)

    def done(self) -> bool:
        return str(self.status().get("state")) in _TERMINAL

    def result(self) -> Any:
        record = self.status()
        if str(record.get("state")) not in _TERMINAL:
            raise RuntimeError("process is not complete")
        if record.get("error") is not None or record.get("outcome") in {
            "failed",
            "cancelled",
        }:
            raise ProcessFailedError(self.process_id, record.get("error"))
        return deepcopy(record.get("result"))

    async def wait_result(
        self,
        *,
        timeout: float | None = None,
        poll_interval: float = 0.01,
    ) -> Any:
        deadline = None if timeout is None else monotonic() + float(timeout)
        while not self.done():
            run_next = getattr(self.engine, "run_next", None)
            if callable(run_next):
                outcome = run_next(self.process_id)
                if hasattr(outcome, "__await__"):
                    await outcome
            if deadline is not None and monotonic() >= deadline:
                raise TimeoutError(f"process {self.process_id} did not complete")
            await asyncio.sleep(max(0.0, float(poll_interval)))
        return self.result()

    def __repr__(self) -> str:
        return f"ProcessHandle(process_id={self.process_id!r}, run_id={self.run_id!r})"
