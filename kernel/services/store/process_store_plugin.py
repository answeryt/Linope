# -*- coding: utf-8 -*-
"""Thread-safe in-memory storage for logical Processes and their runs."""

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
    """Store stable Process identities and immutable-addressed run records."""

    def __init__(self, initial: Mapping[str, Mapping[str, Any]] | None = None) -> None:
        self._items: dict[str, dict[str, Any]] = {}
        self._runs: dict[tuple[str, str], dict[str, Any]] = {}
        self._identities: dict[str, dict[str, Any]] = {}
        self._lock = RLock()
        for record in (initial or {}).values():
            self.create_run(record)

    @staticmethod
    def _record(record: Mapping[str, Any]) -> tuple[str, dict[str, Any]]:
        process_id = record.get(PROCESS_ID)
        if not process_id:
            raise ValueError("record is missing process_id")
        stored = deepcopy(dict(record))
        if not stored.get("run_id"):
            raise ValueError("record is missing run_id")
        return str(process_id), stored

    @staticmethod
    def _run_key(record: Mapping[str, Any]) -> tuple[str, str]:
        return str(record[PROCESS_ID]), str(record["run_id"])

    def _set_current(self, process_id: str, stored: dict[str, Any]) -> None:
        run_id = str(stored["run_id"])
        identity = self._identities.setdefault(
            process_id,
            {
                "process_id": process_id,
                "process_type": stored.get("process_type"),
                "created_at": stored.get("created_at"),
            },
        )
        if (
            identity.get("process_type") is not None
            and stored.get("process_type") != identity.get("process_type")
        ):
            raise ValueError("process_type cannot be changed")
        identity["current_run_id"] = run_id
        identity["updated_at"] = stored.get("updated_at")
        self._items[process_id] = stored

    def put(self, record: Mapping[str, Any]) -> dict[str, Any]:
        """Insert or replace a run and update it when it is the current run."""
        process_id, stored = self._record(record)
        key = self._run_key(stored)
        with self._lock:
            identity = self._identities.get(process_id)
            if identity is None or identity.get("current_run_id") == key[1]:
                self._set_current(process_id, stored)
            self._runs[key] = stored
            return deepcopy(stored)

    def create(self, record: Mapping[str, Any]) -> dict[str, Any]:
        """Create the first run for a new logical Process."""
        process_id, stored = self._record(record)
        with self._lock:
            if process_id in self._identities:
                raise ProcessAlreadyExists(process_id)
            self._set_current(process_id, stored)
            self._runs[self._run_key(stored)] = stored
            return deepcopy(stored)

    def create_run(self, record: Mapping[str, Any]) -> dict[str, Any]:
        """Create and select a new run for an existing or new Process."""
        process_id, stored = self._record(record)
        key = self._run_key(stored)
        with self._lock:
            if key in self._runs:
                raise ProcessAlreadyExists(key)
            identity = self._identities.get(process_id)
            if (
                identity is not None
                and identity.get("process_type") != stored.get("process_type")
            ):
                raise ValueError("process_type cannot be changed")
            self._set_current(process_id, stored)
            self._runs[key] = stored
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

    def get_run(self, process_id: str, run_id: str, default: Any = None) -> Any:
        with self._lock:
            record = self._runs.get((str(process_id), str(run_id)))
            return deepcopy(default if record is None else record)

    def require_run(self, process_id: str, run_id: str) -> dict[str, Any]:
        with self._lock:
            record = self._runs.get((str(process_id), str(run_id)))
            if record is None:
                raise ProcessMissing((process_id, run_id))
            return deepcopy(record)

    def identity(self, process_id: str) -> dict[str, Any] | None:
        with self._lock:
            record = self._identities.get(str(process_id))
            return None if record is None else deepcopy(record)

    def select_run(self, process_id: str, run_id: str) -> dict[str, Any]:
        """Select an existing run as the Process' current run."""
        key = (str(process_id), str(run_id))
        with self._lock:
            record = self._runs.get(key)
            if record is None:
                raise ProcessMissing(key)
            self._set_current(key[0], record)
            return deepcopy(record)

    def list_runs(self, process_id: str) -> list[dict[str, Any]]:
        with self._lock:
            return [
                deepcopy(record)
                for (stored_process_id, _), record in self._runs.items()
                if stored_process_id == str(process_id)
            ]

    def remove(self, process_id: str) -> dict[str, Any] | None:
        with self._lock:
            record = self._items.pop(str(process_id), None)
            self._identities.pop(str(process_id), None)
            for key in [key for key in self._runs if key[0] == str(process_id)]:
                del self._runs[key]
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
            if str(updated.get("run_id")) != str(current.get("run_id")):
                raise ValueError("run_id cannot be changed")
            self._items[key] = updated
            self._runs[self._run_key(updated)] = updated
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
