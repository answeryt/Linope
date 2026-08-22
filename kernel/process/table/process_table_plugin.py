# -*- coding: utf-8 -*-
"""In-memory table of Agent Process records.

Host holds one instance and injects it into lifecycle. This plugin does
not import PCB or state siblings.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Iterator


PLUGIN_NAME = "kernel_process_table"
PLUGIN_VERSION = "1.0"

PROCESS_ID = "process_id"


class ProcessMissing(KeyError):
    """Raised when a process_id is not in the table."""


class ProcessTable:
    """Register, fetch, list, and remove process mappings."""

    def __init__(self, initial: Mapping[str, Mapping[str, Any]] | None = None) -> None:
        self._items: dict[str, dict[str, Any]] = {}
        for record in (initial or {}).values():
            self.put(record)

    def put(self, record: Mapping[str, Any]) -> dict[str, Any]:
        process_id = record.get(PROCESS_ID)
        if not process_id:
            raise ValueError("record is missing process_id")
        stored = dict(record)
        self._items[str(process_id)] = stored
        return dict(stored)

    def get(self, process_id: str, default: Any = None) -> Any:
        record = self._items.get(str(process_id))
        if record is None:
            return default
        return dict(record)

    def require(self, process_id: str) -> dict[str, Any]:
        record = self.get(process_id)
        if record is None:
            raise ProcessMissing(process_id)
        return record

    def remove(self, process_id: str) -> dict[str, Any] | None:
        record = self._items.pop(str(process_id), None)
        return None if record is None else dict(record)

    def list(
        self,
        *,
        parent_id: str | None = None,
        state: str | None = None,
        agent: str | None = None,
    ) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for record in self._items.values():
            if parent_id is not None and record.get("parent_id") != parent_id:
                continue
            if state is not None and record.get("state") != state:
                continue
            if agent is not None and record.get("agent") != agent:
                continue
            result.append(dict(record))
        return result

    def children(self, process_id: str) -> list[dict[str, Any]]:
        return self.list(parent_id=str(process_id))

    def __len__(self) -> int:
        return len(self._items)

    def __iter__(self) -> Iterator[str]:
        return iter(self._items)

    def __contains__(self, process_id: object) -> bool:
        return str(process_id) in self._items
