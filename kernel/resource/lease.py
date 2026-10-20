"""In-process resource lease tracking for capability processes."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from kernel.resource.handle_view import ResourceContext
from kernel.resource.definition import ResourceShareMode


class LeaseStatus(StrEnum):
    ACTIVE = "active"
    RELEASED = "released"


class HandleStatus(StrEnum):
    ACTIVE = "active"
    REVOKED = "revoked"
    RELEASED = "released"


@dataclass(frozen=True)
class ResourceLease:
    lease_id: str
    process_id: str
    resource_id: str
    status: LeaseStatus = LeaseStatus.ACTIVE
    fencing_token: int = 0
    share_mode: ResourceShareMode = ResourceShareMode.EXCLUSIVE


@dataclass
class ResourceEntity:
    resource_id: str
    kind: str
    identity: dict[str, Any]
    status: str = "unloaded"
    refcount: int = 0
    fencing_token: int = 0
    state: dict[str, Any] | None = None


@dataclass(frozen=True)
class HandleRevocation:
    handle: str
    process_id: str
    resource_id: str
    unloaded: tuple[ResourceEntity, ...] = ()


def next_fencing_token(
    share_mode: ResourceShareMode,
    *,
    active_modes: tuple[ResourceShareMode, ...],
    current_token: int,
) -> int:
    """Exclusive leases advance the token. Shared reads keep the current one."""
    if share_mode == ResourceShareMode.EXCLUSIVE:
        if active_modes:
            raise RuntimeError("Resource is already leased")
        return current_token + 1
    if ResourceShareMode.EXCLUSIVE in active_modes:
        raise RuntimeError("Resource is already leased exclusively")
    return current_token


class ResourceLeaseManager:
    """Track exclusive/shared grants, entity refcounts, and handles in memory."""

    def __init__(self) -> None:
        self._leases: dict[str, list[ResourceLease]] = {}
        self._entities: dict[str, ResourceEntity] = {}
        self._handles: dict[str, dict[str, Any]] = {}
        self._pending_loads: dict[str, list[str]] = {}

    def authorize(self, handle: str, process_id: str) -> None:
        """Reject a handle that is not this process's current token."""
        record = self._handles.get(handle)
        if record is None or record["status"] != HandleStatus.ACTIVE:
            raise PermissionError("旧凭证不能再写")
        if str(record["process_id"]) != process_id:
            raise PermissionError("这张句柄不属于这个进程")
        entity = self._entities[str(record["resource_id"])]
        if int(record["fencing_token"]) != int(entity.fencing_token):
            raise PermissionError("旧凭证不能再写")

    def acquire(self, context: ResourceContext) -> tuple[ResourceLease, ...]:
        import uuid

        leases: list[ResourceLease] = []
        pending: list[str] = []
        try:
            for grant in context.grants:
                entity = self._entities.get(grant.resource_id)
                if entity is None:
                    entity = ResourceEntity(
                        resource_id=grant.resource_id,
                        kind=str(getattr(grant.kind, "value", grant.kind)),
                        identity=dict(grant.metadata.get("identity") or {}),
                    )
                    self._entities[grant.resource_id] = entity
                active = [
                    lease
                    for lease in self._leases.get(grant.resource_id, [])
                    if lease.status == LeaseStatus.ACTIVE
                ]
                token = next_fencing_token(
                    grant.share_mode,
                    active_modes=tuple(lease.share_mode for lease in active),
                    current_token=entity.fencing_token,
                )
                if grant.share_mode == ResourceShareMode.EXCLUSIVE:
                    entity.fencing_token = token
                previous_refcount = entity.refcount
                entity.refcount += 1
                if previous_refcount == 0 and entity.status != "loaded":
                    pending.append(grant.resource_id)
                lease = ResourceLease(
                    lease_id=uuid.uuid4().hex,
                    process_id=context.process_id,
                    resource_id=grant.resource_id,
                    fencing_token=token,
                    share_mode=grant.share_mode,
                )
                self._leases.setdefault(grant.resource_id, []).append(lease)
                self._handles[grant.handle] = {
                    "handle": grant.handle,
                    "process_id": context.process_id,
                    "resource_id": grant.resource_id,
                    "fencing_token": token,
                    "status": HandleStatus.ACTIVE,
                }
                leases.append(lease)
        except BaseException:
            self.release(context.process_id)
            raise
        self._pending_loads[context.process_id] = pending
        return tuple(leases)

    def take_pending_loads(self, process_id: str) -> tuple[ResourceEntity, ...]:
        resource_ids = self._pending_loads.pop(process_id, [])
        return tuple(self._entities[resource_id] for resource_id in resource_ids)

    def mark_loaded(self, resource_id: str, state: dict[str, Any]) -> None:
        entity = self._entities[resource_id]
        entity.status = "loaded"
        entity.state = dict(state)

    def mark_unloaded(self, resource_id: str) -> None:
        entity = self._entities.get(resource_id)
        if entity is None:
            return
        entity.status = "unloaded"
        entity.state = None

    def entity(self, resource_id: str) -> ResourceEntity | None:
        return self._entities.get(resource_id)

    def release(self, process_id: str) -> tuple[ResourceEntity, ...]:
        unloaded: list[ResourceEntity] = []
        for resource_id, active in list(self._leases.items()):
            kept: list[ResourceLease] = []
            for lease in active:
                if lease.process_id == process_id and lease.status == LeaseStatus.ACTIVE:
                    entity = self._entities[resource_id]
                    entity.refcount = max(0, entity.refcount - 1)
                    if entity.refcount == 0 and entity.status == "loaded":
                        unloaded.append(entity)
                else:
                    kept.append(lease)
            if kept:
                self._leases[resource_id] = kept
            else:
                self._leases.pop(resource_id, None)
        for handle, record in self._handles.items():
            if (
                record["process_id"] == process_id
                and record["status"] == HandleStatus.ACTIVE
            ):
                record["status"] = HandleStatus.RELEASED
        self._pending_loads.pop(process_id, None)
        return tuple(unloaded)

    def revoke(self, handle: str) -> HandleRevocation:
        record = self._handles.get(handle)
        if record is None or record["status"] != HandleStatus.ACTIVE:
            raise KeyError(handle)
        record["status"] = HandleStatus.REVOKED
        process_id = str(record["process_id"])
        resource_id = str(record["resource_id"])
        unloaded = self._release_resource(process_id, resource_id)
        return HandleRevocation(
            handle=handle,
            process_id=process_id,
            resource_id=resource_id,
            unloaded=tuple(unloaded),
        )

    def active_for(self, process_id: str) -> tuple[ResourceLease, ...]:
        return tuple(
            lease
            for leases in self._leases.values()
            for lease in leases
            if lease.process_id == process_id and lease.status == LeaseStatus.ACTIVE
        )

    def close(self) -> None:
        return None

    def _release_resource(
        self,
        process_id: str,
        resource_id: str,
    ) -> list[ResourceEntity]:
        active = self._leases.get(resource_id, [])
        kept: list[ResourceLease] = []
        unloaded: list[ResourceEntity] = []
        for lease in active:
            if lease.process_id == process_id and lease.status == LeaseStatus.ACTIVE:
                entity = self._entities[resource_id]
                entity.refcount = max(0, entity.refcount - 1)
                if entity.refcount == 0 and entity.status == "loaded":
                    unloaded.append(entity)
            else:
                kept.append(lease)
        if kept:
            self._leases[resource_id] = kept
        else:
            self._leases.pop(resource_id, None)
        return unloaded
