# -*- coding: utf-8 -*-
"""Thread-safe in-memory storage for logical Process records."""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping
from copy import deepcopy
from threading import RLock
from typing import Any


PLUGIN_NAME = "kernel_process_store"
PLUGIN_VERSION = "1.0"

PROCESS_ID = "process_id"


class ProcessMissing(KeyError):
    """Raised when a process is not present in the store."""


class ProcessAlreadyExists(KeyError):
    """Raised when creating a process whose identifier already exists."""


class MemoryProcessStore:
    """Store independent copies of Process mappings under a re-entrant lock."""

    def __init__(self, initial: Mapping[str, Mapping[str, Any]] | None = None) -> None:
        self._items: dict[str, dict[str, Any]] = {}
        self._lock = RLock()
        for record in (initial or {}).values():
            self.put(record)

    @staticmethod
    def _record(record: Mapping[str, Any]) -> tuple[str, dict[str, Any]]:
        process_id = record.get(PROCESS_ID)
        if not process_id:
            raise ValueError("record is missing process_id")
        return str(process_id), deepcopy(dict(record))

    def put(self, record: Mapping[str, Any]) -> dict[str, Any]:
        """Insert or replace a record."""
        process_id, stored = self._record(record)
        with self._lock:
            self._items[process_id] = stored
            return deepcopy(stored)

    def create(self, record: Mapping[str, Any]) -> dict[str, Any]:
        """Atomically insert a record, rejecting duplicate identifiers."""
        process_id, stored = self._record(record)
        with self._lock:
            if process_id in self._items:
                raise ProcessAlreadyExists(process_id)
            self._items[process_id] = stored
            return deepcopy(stored)

    def get(self, process_id: str, default: Any = None) -> Any:
        with self._lock:
            record = self._items.get(str(process_id))
            return deepcopy(default if record is None else record)

    def require(self, process_id: str) -> dict[str, Any]:
        with self._lock:
            record = self._items.get(str(process_id))
            if record is None:
                raise ProcessMissing(process_id)
            return deepcopy(record)

    def remove(self, process_id: str) -> dict[str, Any] | None:
        with self._lock:
            record = self._items.pop(str(process_id), None)
            return deepcopy(record)

    def update(
        self,
        process_id: str,
        changes: Mapping[str, Any] | Callable[[dict[str, Any]], Mapping[str, Any] | None],
    ) -> dict[str, Any]:
        """Atomically update a record with a mapping or mutation callback."""
        key = str(process_id)
        with self._lock:
            current = self._items.get(key)
            if current is None:
                raise ProcessMissing(process_id)
            updated = deepcopy(current)
            if callable(changes):
                result = changes(updated)
                if result is not None:
                    updated = deepcopy(dict(result))
            else:
                updated.update(deepcopy(dict(changes)))
            updated_id = updated.get(PROCESS_ID)
            if not updated_id:
                raise ValueError("updated record is missing process_id")
            if str(updated_id) != key:
                raise ValueError("process_id cannot be changed")
            self._items[key] = updated
            return deepcopy(updated)

    def list(
        self,
        *,
        state: str | None = None,
        process_type: str | None = None,
    ) -> list[dict[str, Any]]:
        with self._lock:
            return [
                deepcopy(record)
                for record in self._items.values()
                if (state is None or record.get("state") == state)
                and (process_type is None or record.get("process_type") == process_type)
            ]

    def __len__(self) -> int:
        with self._lock:
            return len(self._items)

    def __iter__(self) -> Iterator[str]:
        with self._lock:
            return iter(tuple(self._items))

    def __contains__(self, process_id: object) -> bool:
        with self._lock:
            return str(process_id) in self._items


ProcessTable = MemoryProcessStore
