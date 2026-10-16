"""One saved document made of resource, process, mailbox, and channel sections."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from kernel.communication.ledger.channel_state import ChannelSection
from kernel.communication.ledger.requests import MailboxSection
from kernel.communication.ledger_contracts import ChannelStore, RequestStore
from kernel.process.process_manager.ledger_contracts import (
    ReconcileStore,
    ResourceRuntimeStore,
)
from kernel.process.process_manager.process_ledger import ProcessSection
from kernel.resource.store.file_store import FileStore
from kernel.resource.store.registry import (
    open_store,
    register_store,
    store_names,
    unregister_store,
)
from kernel.resource.store.registry import local_path_for as local_path
from kernel.resource.store.resource_section import ResourceSection
from kernel.resource.store.sections import export_sections, import_sections

__all__ = [
    "ChannelStore",
    "FileResourceStore",
    "MemoryResourceStore",
    "ReconcileStore",
    "RequestStore",
    "ResourceRuntimeStore",
    "open_store",
    "register_store",
    "store_names",
    "unregister_store",
]


class MemoryResourceStore:
    """In-memory ledger. Sections share one lock and one saved document."""

    def __init__(self, *, locator: str = "memory:", reap: bool = False) -> None:
        self.locator = locator
        self.path = None
        self._lock = threading.RLock()
        self.resource = ResourceSection(self._lock)
        self.process = ProcessSection(self._lock)
        self.mailbox = MailboxSection(self._lock)
        self.channel = ChannelSection(self._lock)
        self._sections = (
            self.resource,
            self.process,
            self.mailbox,
            self.channel,
        )
        if reap:
            self.reap_dead_processes()

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        for section in self._sections:
            method = getattr(section, name, None)
            if callable(method):
                return method
        raise AttributeError(name)

    def reap_dead_processes(self) -> None:
        from kernel.process.process_manager.liveness import process_matches

        with self._lock:
            for process_id, record in self.process.rows():
                if record.get("status") not in {"starting", "running"}:
                    continue
                if process_matches(record.get("pid"), record.get("identity")):
                    continue
                unloaded = self.resource.release(process_id)
                for entity in unloaded:
                    self.resource.mark_unloaded(entity.resource_id)
                self.process.update_process(
                    process_id,
                    status="failed",
                    exit_code=None,
                )

    def resource_seats(
        self,
        kind: str,
        identity: dict[str, Any],
    ) -> tuple[dict[str, Any], ...]:
        """Read who still holds this resource and how full each mailbox is."""
        with self._lock:
            seats: list[dict[str, Any]] = []
            for resource_id, entity, lease, handle in self.resource.active_lease_rows():
                if entity.kind != kind or not _same_identity(entity.identity, identity):
                    continue
                process = self.process.get_process(lease.process_id)
                if process is None:
                    continue
                if process.get("status") not in {"starting", "running"}:
                    continue
                if process.get("desired") == "stop":
                    continue
                seats.append(
                    self._seat(
                        lease.process_id,
                        resource_id=resource_id,
                        kind=entity.kind,
                        identity=dict(entity.identity),
                        share_mode=lease.share_mode.value,
                        handle=handle,
                        process=process,
                    )
                )
            return tuple(seats)

    def capability_seats(self, capability_id: str) -> tuple[dict[str, Any], ...]:
        """Running processes of one capability, grouped by whether they are shared."""
        with self._lock:
            shared = self.process.shares_capability(capability_id)
            seats: list[dict[str, Any]] = []
            for row in self.process.running_processes(capability_id):
                process_id = str(row["process_id"])
                process = self.process.get_process(process_id)
                if process is None:
                    continue
                seats.append(
                    self._seat(
                        process_id,
                        resource_id=capability_id if shared else process_id,
                        kind="",
                        identity={"capability": capability_id},
                        share_mode="shared" if shared else "exclusive",
                        handle="",
                        process=process,
                    )
                )
            return tuple(seats)

    def submit_request(
        self,
        process_id: str,
        body: dict[str, Any],
        sender_id: str | None = None,
    ) -> str:
        """Hand one mailbox body over, and charge its size to the sender."""
        request_id = self.mailbox.submit_request(process_id, body, sender_id)
        from kernel.resource.account.recorded import record_communication

        record_communication(self, sender_id or process_id, body)
        return request_id

    def complete_request(
        self,
        request_id: str,
        reply: dict[str, Any],
        claim_token: str | None = None,
    ) -> None:
        """Store a reply when the scheduled checks still hold."""
        from kernel.communication.ledger.requests import allow_commit

        if not allow_commit(self, str(request_id), read=_read_representation):
            schedule = self.mailbox.request_schedule(str(request_id)) or {}
            token = schedule.get("claim_token")
            if claim_token is None or token is None or claim_token == token:
                self.mailbox.requeue_request(str(request_id))
            return
        self.mailbox.complete_request(request_id, reply, claim_token)

    def _seat(
        self,
        process_id: str,
        *,
        resource_id: str,
        kind: str,
        identity: dict[str, Any],
        share_mode: str,
        handle: str,
        process: dict[str, Any],
    ) -> dict[str, Any]:
        pending, claimed = self.mailbox.mailbox_counts(process_id)
        limits, capacity = _seat_limits(process)
        occupied, window = _context_snapshot(self, process_id)
        rtt_ms = _rtt_ms(self, process_id)
        return {
            "process_id": process_id,
            "resource_id": resource_id,
            "capability_id": process.get("capability_id") or "",
            "kind": kind,
            "identity": identity,
            "pending": pending,
            "claimed": claimed,
            "limits": limits,
            "capacity": capacity,
            "occupied": occupied,
            "window": window,
            "share_mode": share_mode,
            "handle": handle,
            "rtt_ms": rtt_ms,
        }

    def initialize_schema(self) -> None:
        return None

    def migrate(self) -> None:
        return None

    def check(self) -> dict[str, Any]:
        return {
            "locator": self.locator,
            "backend": "memory",
            "ready": True,
            "persistent": False,
        }

    def export_state(self) -> dict[str, Any]:
        with self._lock:
            return export_sections(self._sections)

    def import_state(self, payload: dict[str, Any]) -> None:
        with self._lock:
            import_sections(self._sections, payload)

    def close(self) -> None:
        return None

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.locator!r})"


class FileResourceStore(FileStore):
    """File ledger wired with every section."""

    def __init__(self, path: str | Path, *, reap: bool = True) -> None:
        expanded = Path(path).expanduser()
        super().__init__(
            expanded,
            memory=MemoryResourceStore(locator=f"file:{expanded}", reap=False),
            reap=reap,
        )


def _read_representation(href: str) -> dict[str, Any]:
    """Read one representation for a mailbox commit check."""
    from kernel.hypermedia.observation import fetch_representation

    return fetch_representation(href)


def _file_store(locator: str, *, reap: bool = True):
    return FileResourceStore(local_path(locator), reap=reap)


def _memory_store(locator: str, *, reap: bool = True):
    return MemoryResourceStore(locator=locator, reap=reap)


def _database_store(locator: str, *, reap: bool = True):
    from kernel.database.store import DatabaseStore

    return DatabaseStore(
        locator,
        memory=MemoryResourceStore(locator=locator, reap=False),
        reap=reap,
    )


def _install_builtins() -> None:
    register_store("file", _file_store, builtin=True)
    register_store("memory", _memory_store, builtin=True)
    register_store("database", _database_store)


def _same_identity(left: dict[str, Any], right: dict[str, Any]) -> bool:
    return json.dumps(left, sort_keys=True, default=str) == json.dumps(
        right, sort_keys=True, default=str
    )


def _rtt_ms(store: Any, process_id: str) -> int:
    note = store.note(process_id, "rtt") if hasattr(store, "note") else {}
    if not isinstance(note, dict) or "ms" not in note:
        return 0
    return int(note["ms"])


def _context_snapshot(store: Any, process_id: str) -> tuple[int, int | None]:
    note = store.note(process_id, "context") if hasattr(store, "note") else {}
    if not isinstance(note, dict) or not note:
        return 0, None
    ceiling = note.get("ceiling")
    return int(note.get("occupied", 0)), None if ceiling is None else int(ceiling)


def _seat_limits(process: dict[str, Any]) -> tuple[dict[str, Any], int]:
    activation = process.get("activation")
    if not isinstance(activation, dict):
        activation = {}
    policy = activation.get("thread_policy")
    if not isinstance(policy, dict):
        policy = {}
    limits: dict[str, Any] = {}
    context = activation.get("resource_context")
    grants = context.get("grants") if isinstance(context, dict) else None
    if isinstance(grants, list):
        for grant in grants:
            if isinstance(grant, dict) and isinstance(grant.get("limits"), dict):
                limits.update(grant["limits"])
    if process.get("inflight_ceiling") is not None:
        capacity = int(process["inflight_ceiling"])
    elif process.get("worker_ceiling") is not None:
        capacity = int(process["worker_ceiling"])
    else:
        capacity = int(policy.get("max_concurrent_tasks", 1))
    return limits, max(1, capacity)


_install_builtins()
