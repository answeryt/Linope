"""Contracts for execution inside one capability process."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class ThreadPolicy:
    """Process-local concurrency limits.

    ``max_concurrent_tasks`` limits both async and sync requests.  The sync
    worker pool has its own limit because async requests do not need an OS
    worker thread while waiting for I/O.
    """

    max_concurrent_tasks: int = 1
    min_concurrent_tasks: int = 1
    max_sync_workers: int = 1
    claim_lease_seconds: float = 120.0
    shutdown_timeout_seconds: float = 5.0
    poll_interval_seconds: float = 0.05
    session_affinity: bool = False

    def __post_init__(self) -> None:
        if self.max_concurrent_tasks < 1:
            raise ValueError("max_concurrent_tasks must be at least 1")
        if self.min_concurrent_tasks < 1:
            raise ValueError("min_concurrent_tasks must be at least 1")
        if self.min_concurrent_tasks > self.max_concurrent_tasks:
            raise ValueError("min_concurrent_tasks cannot exceed max_concurrent_tasks")
        if self.max_sync_workers < 0:
            raise ValueError("max_sync_workers must not be negative")
        if self.claim_lease_seconds <= 0:
            raise ValueError("claim_lease_seconds must be positive")
        if self.shutdown_timeout_seconds < 0:
            raise ValueError("shutdown_timeout_seconds must not be negative")
        if self.poll_interval_seconds < 0:
            raise ValueError("poll_interval_seconds must not be negative")

    def payload(self) -> dict[str, Any]:
        return {
            "max_concurrent_tasks": self.max_concurrent_tasks,
            "min_concurrent_tasks": self.min_concurrent_tasks,
            "max_sync_workers": self.max_sync_workers,
            "claim_lease_seconds": self.claim_lease_seconds,
            "shutdown_timeout_seconds": self.shutdown_timeout_seconds,
            "poll_interval_seconds": self.poll_interval_seconds,
            "session_affinity": self.session_affinity,
        }

    @classmethod
    def from_payload(cls, payload: dict[str, Any] | None) -> "ThreadPolicy":
        raw = dict(payload or {})
        return cls(
            max_concurrent_tasks=int(raw.get("max_concurrent_tasks", 1)),
            min_concurrent_tasks=int(raw.get("min_concurrent_tasks", 1)),
            max_sync_workers=int(raw.get("max_sync_workers", 1)),
            claim_lease_seconds=float(raw.get("claim_lease_seconds", 120.0)),
            shutdown_timeout_seconds=float(
                raw.get("shutdown_timeout_seconds", 5.0)
            ),
            poll_interval_seconds=float(raw.get("poll_interval_seconds", 0.05)),
            session_affinity=bool(raw.get("session_affinity", False)),
        )


@dataclass(frozen=True)
class ClaimedRequest:
    """A request reserved by one in-process execution unit."""

    request_id: str
    process_id: str
    body: dict[str, Any]
    claim_token: str = field(default_factory=lambda: uuid.uuid4().hex)
    worker_id: str = ""


class ThreadInbox(Protocol):
    """Synchronous bridge used by the async runtime.

    Implementations must make ``claim`` atomic for a process id.  The runtime
    calls these short ledger operations through a bridge so a slow persistent
    store cannot block the event loop.
    """

    def claim(
        self,
        process_id: str,
        worker_id: str,
        lease_seconds: float,
    ) -> ClaimedRequest | None:
        ...

    def complete(
        self,
        request_id: str,
        reply: dict[str, Any],
        claim_token: str | None = None,
    ) -> None:
        ...

    def lookup(self, request_id: str) -> dict[str, Any] | None:
        ...


class ThreadAdapter(Protocol):
    """Optional adapter shape consumed by :class:`ThreadRuntime`."""

    def handle(self, request: dict[str, Any]) -> Any:
        ...
