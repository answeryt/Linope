# -*- coding: utf-8 -*-
"""Thread-safe persistence for idempotent Continuation Records."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from datetime import datetime, timezone
from threading import RLock
from typing import Any


PLUGIN_NAME = "kernel_continuation_store"
PLUGIN_VERSION = "1.0"


class ContinuationConflict(ValueError):
    """Raised when one continuation ID is reused with different semantics."""


class MemoryContinuationStore:
    """Keep portable continuation intents independently from Process state."""

    def __init__(self) -> None:
        self._items: dict[str, dict[str, Any]] = {}
        self._lock = RLock()

    @staticmethod
    def _semantic(record: Mapping[str, Any]) -> dict[str, Any]:
        return {
            key: deepcopy(record.get(key))
            for key in (
                "process_id",
                "run_id",
                "source_execution_id",
                "sequence",
                "reason",
                "input",
                "when",
                "priority",
            )
        }

    def create(self, record: Mapping[str, Any]) -> dict[str, Any]:
        stored = deepcopy(dict(record))
        continuation_id = str(stored.get("continuation_id") or "")
        if not continuation_id:
            raise ValueError("continuation_id is required")
        with self._lock:
            existing = self._items.get(continuation_id)
            if existing is not None:
                if self._semantic(existing) != self._semantic(stored):
                    raise ContinuationConflict(continuation_id)
                return deepcopy(existing)
            self._items[continuation_id] = stored
            return deepcopy(stored)

    def get(self, continuation_id: str, default: Any = None) -> Any:
        with self._lock:
            record = self._items.get(str(continuation_id))
            return deepcopy(default if record is None else record)

    def require(self, continuation_id: str) -> dict[str, Any]:
        record = self.get(continuation_id)
        if record is None:
            raise KeyError(continuation_id)
        return record

    def list(
        self,
        *,
        status: str | None = None,
        process_id: str | None = None,
    ) -> list[dict[str, Any]]:
        with self._lock:
            return [
                deepcopy(record)
                for record in self._items.values()
                if (status is None or record.get("status") == status)
                and (
                    process_id is None
                    or record.get("process_id") == str(process_id)
                )
            ]

    def update(
        self, continuation_id: str, **changes: Any
    ) -> dict[str, Any]:
        key = str(continuation_id)
        with self._lock:
            record = self._items.get(key)
            if record is None:
                raise KeyError(key)
            record.update(deepcopy(changes))
            return deepcopy(record)

    def claim(self, continuation_id: str) -> dict[str, Any] | None:
        """Atomically reserve one pending intent for dispatch."""
        key = str(continuation_id)
        with self._lock:
            record = self._items.get(key)
            if record is None:
                raise KeyError(key)
            if record.get("status") != "pending":
                return None
            record["status"] = "dispatching"
            return deepcopy(record)

    def release(self, continuation_id: str) -> dict[str, Any]:
        """Return a failed dispatch claim to the pending state."""
        key = str(continuation_id)
        with self._lock:
            record = self._items.get(key)
            if record is None:
                raise KeyError(key)
            if record.get("status") == "dispatching":
                record["status"] = "pending"
            return deepcopy(record)

    def mark_dispatched(
        self, continuation_id: str, *, activation_id: str
    ) -> dict[str, Any]:
        record = self.require(continuation_id)
        if record.get("status") == "dispatched":
            if record.get("activation_id") != str(activation_id):
                raise ContinuationConflict(continuation_id)
            return record
        return self.update(
            continuation_id,
            status="dispatched",
            activation_id=str(activation_id),
            dispatched_at=datetime.now(timezone.utc).isoformat(),
        )

    def mark_consumed(self, continuation_id: str) -> dict[str, Any]:
        return self.update(
            continuation_id,
            status="consumed",
            consumed_at=datetime.now(timezone.utc).isoformat(),
        )

    def cancel(self, continuation_id: str) -> dict[str, Any]:
        return self.update(continuation_id, status="cancelled")

    def observe(
        self,
        continuation_id: str,
        *,
        event: Mapping[str, Any] | None = None,
        latches: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Append an observed fact and merge spatiotemporal latch progress."""
        key = str(continuation_id)
        with self._lock:
            record = self._items.get(key)
            if record is None:
                raise KeyError(key)
            facts = record.setdefault("facts", {"events": [], "latches": {}})
            facts.setdefault("events", [])
            facts.setdefault("latches", {})
            if event is not None:
                facts["events"].append(deepcopy(dict(event)))
            if latches:
                facts["latches"].update(deepcopy(dict(latches)))
            return deepcopy(record)
