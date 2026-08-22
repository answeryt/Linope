# -*- coding: utf-8 -*-
"""In-memory table of Agent Thread records.

Host holds one instance per Agent Process table and injects it into
lifecycle. This plugin does not import context or state siblings.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Iterator


PLUGIN_NAME = "kernel_thred_table"
PLUGIN_VERSION = "1.0"

THREAD_ID = "thread_id"


class ThreadMissing(KeyError):
    """Raised when a thread_id is not in the table."""


class ThreadTable:
    """Register, fetch, list, and remove thread mappings."""

    def __init__(self, initial: Mapping[str, Mapping[str, Any]] | None = None) -> None:
        self._items: dict[str, dict[str, Any]] = {}
        for record in (initial or {}).values():
            self.put(record)

    def put(self, record: Mapping[str, Any]) -> dict[str, Any]:
        thread_id = record.get(THREAD_ID)
        if not thread_id:
            raise ValueError("record is missing thread_id")
        stored = dict(record)
        self._items[str(thread_id)] = stored
        return dict(stored)

    def get(self, thread_id: str, default: Any = None) -> Any:
        record = self._items.get(str(thread_id))
        if record is None:
            return default
        return dict(record)

    def require(self, thread_id: str) -> dict[str, Any]:
        record = self.get(thread_id)
        if record is None:
            raise ThreadMissing(thread_id)
        return record

    def remove(self, thread_id: str) -> dict[str, Any] | None:
        record = self._items.pop(str(thread_id), None)
        return None if record is None else dict(record)

    def list(
        self,
        *,
        process_id: str | None = None,
        parent_id: str | None = None,
        state: str | None = None,
        wait_reason: str | None = None,
    ) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for record in self._items.values():
            if process_id is not None and record.get("process_id") != process_id:
                continue
            if parent_id is not None and record.get("parent_id") != parent_id:
                continue
            if state is not None and record.get("state") != state:
                continue
            if wait_reason is not None and record.get("wait_reason") != wait_reason:
                continue
            result.append(dict(record))
        return result

    def for_process(self, process_id: str) -> list[dict[str, Any]]:
        return self.list(process_id=str(process_id))

    def __len__(self) -> int:
        return len(self._items)

    def __iter__(self) -> Iterator[str]:
        return iter(self._items)

    def __contains__(self, thread_id: object) -> bool:
        return str(thread_id) in self._items
