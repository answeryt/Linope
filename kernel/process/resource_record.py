"""One resource account per process.

The contract says which fields exist. This module keeps one in-memory table
per pid. The ledger file is a copy of those tables and nothing else.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from kernel.resource.resource_contract import kind_name


class RecordStatus(StrEnum):
    OPENING = "opening"
    READY = "ready"
    CLOSING = "closing"
    CLOSED = "closed"


@dataclass
class HeldResource:
    """One line on a process account. The body of the resource is not copied."""

    lease_id: str
    kind: str
    resource_id: str
    share_mode: str
    fencing_token: int
    handle: str
    identity: dict[str, Any]


@dataclass
class ProcessResourceRecord:
    """The only account for one process."""

    pid: int
    capability_id: str
    status: RecordStatus = RecordStatus.OPENING
    claims: list[dict[str, Any]] = field(default_factory=list)
    leases: list[HeldResource] = field(default_factory=list)
    room: dict[str, Any] = field(default_factory=dict)
    started: str = ""

    def payload(self) -> dict[str, Any]:
        """The fields the ledger is allowed to store."""
        return {
            "pid": self.pid,
            "capability_id": self.capability_id,
            "status": self.status.value,
            "claims": [dict(item) for item in self.claims],
            "leases": [
                {
                    "lease_id": item.lease_id,
                    "kind": item.kind,
                    "resource_id": item.resource_id,
                    "share_mode": item.share_mode,
                    "fencing_token": item.fencing_token,
                    "handle": item.handle,
                    "identity": dict(item.identity),
                }
                for item in self.leases
            ],
            "room": dict(self.room),
            "started": self.started,
        }


class ProcessResourceBook:
    """Every live process account, keyed by pid."""

    def __init__(self, ledger: Any | None = None) -> None:
        self._records: dict[int, ProcessResourceRecord] = {}
        self._ledger = ledger
        if ledger is not None:
            for item in ledger.read():
                record = record_from_payload(item)
                if record is None:
                    continue
                self._records[record.pid] = record

    def open(self, pid: int, capability_id: str) -> ProcessResourceRecord:
        pid = int(pid)
        if pid <= 0:
            raise RuntimeError(f"Invalid pid: {pid}")
        current = self._records.get(pid)
        if current is not None and current.status != RecordStatus.CLOSED:
            raise RuntimeError(f"This process already has a record: {pid}")
        self._forget_activity(pid)
        record = ProcessResourceRecord(
            pid=pid,
            capability_id=capability_id,
        )
        self._records[pid] = record
        self.save()
        return record

    def get(self, pid: int) -> ProcessResourceRecord | None:
        return self._records.get(int(pid))

    def _require_open(self, pid: int) -> ProcessResourceRecord:
        record = self._records.get(int(pid))
        if record is None or record.status != RecordStatus.OPENING:
            raise RuntimeError(f"This process has no open record: {pid}")
        return record

    def attach(
        self,
        pid: int,
        *,
        claims: tuple[dict[str, Any], ...] | list[dict[str, Any]],
        leases: tuple[HeldResource, ...] | list[HeldResource],
        room: dict[str, Any],
    ) -> None:
        record = self._require_open(pid)
        record.claims = [dict(item) for item in claims]
        record.leases = list(leases)
        record.room = dict(room)
        record.status = RecordStatus.READY
        self.save()

    def note_os(self, pid: int, started: str) -> None:
        """Remember when this operating-system process was created."""
        record = self._records.get(int(pid))
        if record is None:
            return
        record.started = started
        self.save()

    def records(self) -> tuple[ProcessResourceRecord, ...]:
        return tuple(self._records.values())

    def handles_for(self, pid: int) -> tuple[str, ...]:
        record = self._records.get(int(pid))
        if record is None or record.status == RecordStatus.CLOSED:
            return ()
        return tuple(item.handle for item in record.leases)

    def close(self, pid: int) -> ProcessResourceRecord | None:
        """Mark the account closed. A second close does nothing."""
        record = self._records.get(int(pid))
        if record is None or record.status == RecordStatus.CLOSED:
            return record
        record.status = RecordStatus.CLOSING
        record.status = RecordStatus.CLOSED
        self.save()
        return record

    def discard(self, pid: int) -> None:
        """Drop an account that never became ready, so the book does not keep it."""
        self._records.pop(int(pid), None)
        self.save()

    def _forget_activity(self, pid: int) -> None:
        ledger = self._ledger
        if ledger is None:
            return
        from pathlib import Path

        from kernel.trace.activity import ActivityLog

        ActivityLog(Path(ledger.path).with_name("activity.jsonl")).forget(pid)

    def save(self) -> None:
        if self._ledger is None:
            return
        self._ledger.write([record.payload() for record in self._records.values()])


def record_from_payload(item: dict[str, Any]) -> ProcessResourceRecord | None:
    """One account restored from the ledger file. Rows without a pid are dropped."""
    pid = int(item.get("pid") or 0)
    if pid <= 0:
        return None
    return ProcessResourceRecord(
        pid=pid,
        capability_id=str(item["capability_id"]),
        status=RecordStatus(str(item["status"])),
        claims=[dict(claim) for claim in item.get("claims") or ()],
        leases=[
            HeldResource(
                lease_id=str(lease["lease_id"]),
                kind=str(lease["kind"]),
                resource_id=str(lease["resource_id"]),
                share_mode=str(lease["share_mode"]),
                fencing_token=int(lease["fencing_token"]),
                handle=str(lease["handle"]),
                identity=dict(lease.get("identity") or {}),
            )
            for lease in item.get("leases") or ()
        ],
        room=dict(item.get("room") or {}),
        started=str(item.get("started") or ""),
    )


def held_from_grant(grant: Any, lease: Any) -> HeldResource:
    """One account line from a grant and the lease the pool already issued."""
    identity = {}
    metadata = getattr(grant, "metadata", {}) or {}
    if isinstance(metadata, dict):
        identity = dict(metadata.get("identity") or {})
    return HeldResource(
        lease_id=str(lease.lease_id),
        kind=kind_name(grant.kind),
        resource_id=str(grant.resource_id),
        share_mode=kind_name(grant.share_mode),
        fencing_token=int(lease.fencing_token),
        handle=str(grant.handle),
        identity=identity,
    )
