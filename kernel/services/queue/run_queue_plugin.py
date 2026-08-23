# -*- coding: utf-8 -*-
"""Thread-safe in-memory queue with leases and fencing tokens."""

from __future__ import annotations

import time
from copy import deepcopy
from threading import RLock
from typing import Any
from uuid import uuid4


PLUGIN_NAME = "kernel_run_queue"
PLUGIN_VERSION = "1.0"

ENQUEUED = "ENQUEUED"
CLAIMED = "CLAIMED"
ACKED = "ACKED"


class InMemoryRunQueue:
    """Prioritized FIFO queue using monotonic time for availability and leases."""

    def __init__(self) -> None:
        self._items: dict[str, dict[str, Any]] = {}
        self._deduplication: dict[str, str] = {}
        self._sequence = 0
        self._lock = RLock()

    def enqueue(
        self,
        kind: str,
        target_id: str,
        payload: Any = None,
        priority: int = 0,
        available_at: float | None = None,
        deduplication_key: str | None = None,
    ) -> dict[str, Any]:
        if not kind:
            raise ValueError("kind is required")
        if not target_id:
            raise ValueError("target_id is required")
        now = time.monotonic()
        with self._lock:
            if deduplication_key is not None:
                existing_id = self._deduplication.get(str(deduplication_key))
                if existing_id is not None:
                    return deepcopy(self._items[existing_id])
            self._sequence += 1
            item_id = uuid4().hex
            item = {
                "item_id": item_id,
                "kind": str(kind),
                "target_id": str(target_id),
                "payload": deepcopy(payload),
                "priority": int(priority),
                "available_at": now if available_at is None else float(available_at),
                "deduplication_key": (
                    None if deduplication_key is None else str(deduplication_key)
                ),
                "state": ENQUEUED,
                "worker_id": None,
                "fencing_token": 0,
                "lease_expires_at": None,
                "last_error": None,
                "attempts": 0,
                "sequence": self._sequence,
            }
            self._items[item_id] = item
            if deduplication_key is not None:
                self._deduplication[str(deduplication_key)] = item_id
            return deepcopy(item)

    def claim(
        self,
        worker_id: str,
        lease_seconds: float = 30,
        kind: str | None = None,
    ) -> dict[str, Any] | None:
        if not worker_id:
            raise ValueError("worker_id is required")
        if lease_seconds <= 0:
            raise ValueError("lease_seconds must be positive")
        now = time.monotonic()
        with self._lock:
            candidates = [
                item
                for item in self._items.values()
                if (kind is None or item["kind"] == kind)
                and (
                    (item["state"] == ENQUEUED and item["available_at"] <= now)
                    or (
                        item["state"] == CLAIMED
                        and item["lease_expires_at"] is not None
                        and item["lease_expires_at"] <= now
                    )
                )
            ]
            if not candidates:
                return None
            item = min(candidates, key=lambda value: (-value["priority"], value["sequence"]))
            item["state"] = CLAIMED
            item["worker_id"] = str(worker_id)
            item["fencing_token"] += 1
            item["lease_expires_at"] = now + float(lease_seconds)
            item["attempts"] += 1
            return deepcopy(item)

    @staticmethod
    def _owns_claim(
        item: dict[str, Any] | None,
        worker_id: str,
        fencing_token: int,
    ) -> bool:
        return bool(
            item is not None
            and item["state"] == CLAIMED
            and item["worker_id"] == str(worker_id)
            and item["fencing_token"] == int(fencing_token)
        )

    def ack(self, item_id: str, worker_id: str, fencing_token: int) -> bool:
        """Acknowledge only the currently fenced claim."""
        with self._lock:
            item = self._items.get(str(item_id))
            if not self._owns_claim(item, worker_id, fencing_token):
                return False
            assert item is not None
            item["state"] = ACKED
            item["worker_id"] = None
            item["lease_expires_at"] = None
            return True

    def retry(
        self,
        item_id: str,
        worker_id: str,
        fencing_token: int,
        delay_seconds: float = 0,
        error: Any = None,
    ) -> bool:
        """Return the currently fenced claim to the queue after a delay."""
        if delay_seconds < 0:
            raise ValueError("delay_seconds cannot be negative")
        with self._lock:
            item = self._items.get(str(item_id))
            if not self._owns_claim(item, worker_id, fencing_token):
                return False
            assert item is not None
            item["state"] = ENQUEUED
            item["available_at"] = time.monotonic() + float(delay_seconds)
            item["worker_id"] = None
            item["lease_expires_at"] = None
            item["last_error"] = deepcopy(error)
            return True

    def recover_expired_claims(self) -> int:
        """Requeue expired claims and invalidate their current ownership."""
        now = time.monotonic()
        recovered = 0
        with self._lock:
            for item in self._items.values():
                if (
                    item["state"] == CLAIMED
                    and item["lease_expires_at"] is not None
                    and item["lease_expires_at"] <= now
                ):
                    item["state"] = ENQUEUED
                    item["available_at"] = now
                    item["worker_id"] = None
                    item["lease_expires_at"] = None
                    recovered += 1
        return recovered

    def get(self, item_id: str, default: Any = None) -> Any:
        with self._lock:
            item = self._items.get(str(item_id))
            return deepcopy(default if item is None else item)

    def list(self, *, state: str | None = None, kind: str | None = None) -> list[dict[str, Any]]:
        with self._lock:
            return [
                deepcopy(item)
                for item in self._items.values()
                if (state is None or item["state"] == state)
                and (kind is None or item["kind"] == kind)
            ]
