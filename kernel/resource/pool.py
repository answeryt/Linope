"""Kind-routed resource pool: leases, refcounted entities, and handles."""

from __future__ import annotations

import secrets
import threading
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any, Protocol

from kernel.resource.compile import CompiledResource
from kernel.resource.handle_view import ResourceContext
from kernel.resource.definition import ResourceGrant
from kernel.resource.lease import HandleRevocation, ResourceEntity
from kernel.resource.resource_contract import close_entity, kind_name, open_entity

PoolListener = Callable[[dict[str, Any]], None]


class ResourcePoolStore(Protocol):
    """Lease slice required by the resource pool.

    Process rows live on the process ledger. The pool only acquires, loads,
    and releases resource entities.
    """

    def acquire(self, context: ResourceContext) -> Any:
        ...

    def take_pending_loads(self, pid: int) -> tuple[ResourceEntity, ...]:
        ...

    def release(self, pid: int) -> tuple[ResourceEntity, ...]:
        ...

    def authorize(self, handle: str, pid: int) -> None:
        ...

    def revoke(self, handle: str) -> HandleRevocation:
        ...

    def mark_loaded(self, resource_id: str, state: dict[str, Any]) -> None:
        ...

    def mark_unloaded(self, resource_id: str) -> None:
        ...


class RecordingLoader:
    """Remember that an entity is loaded without fetching real weights or tools."""

    def load(self, kind: str, identity: dict[str, Any]) -> dict[str, Any]:
        return {
            "loaded": True,
            "kind": kind_name(kind),
            "identity": dict(identity),
        }

    def unload(
        self,
        kind: str,
        identity: dict[str, Any],
        state: dict[str, Any] | None,
    ) -> None:
        return None


class ResourcePool:
    """Approve leases, load entities when the refcount leaves zero, mint handles."""

    def __init__(
        self,
        store: ResourcePoolStore,
        loader: Any | None = None,
        listener: PoolListener | None = None,
    ) -> None:
        self.store = store
        self.loader = loader or RecordingLoader()
        self._listener = listener
        self._lock = threading.Lock()
        self._grants_for_process: dict[int, tuple[ResourceGrant, ...]] = {}
        self.book = None

    def bind(
        self,
        pid: int,
        capability_id: str,
        compiled: tuple[CompiledResource, ...],
    ) -> tuple[ResourceGrant, ...]:
        grants = tuple(_grant_for(item) for item in compiled)
        context = ResourceContext(
            pid=pid,
            capability_id=capability_id,
            grants=grants,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        error: BaseException | None = None
        with self._lock:
            try:
                self.store.acquire(context)
                self._grants_for_process[pid] = grants
                pending = self.store.take_pending_loads(pid)
            except BaseException as exc:
                unloaded = self._take_release(pid)
                error = exc
            else:
                unloaded = ()
        if error is not None:
            self._unload_all(unloaded)
            raise error
        try:
            for entity in pending:
                self._load_entity(pid, entity, grants)
        except BaseException:
            with self._lock:
                unloaded = self._take_release(pid)
            self._unload_all(unloaded)
            raise
        return grants

    def grants_for(self, pid: int) -> tuple[ResourceGrant, ...]:
        return self._grants_for_process[pid]

    def release(self, pid: int) -> tuple[ResourceEntity, ...]:
        with self._lock:
            unloaded = self._take_release(pid)
        self._unload_all(unloaded)
        return unloaded

    def authorize(self, handle: str, pid: int) -> None:
        """The lease is the only place that refuses a handle."""
        with self._lock:
            self.store.authorize(handle, pid)

    def revoke(self, handle: str) -> HandleRevocation:
        with self._lock:
            revocation = self.store.revoke(handle)
        self._unload_all(revocation.unloaded)
        self.notify(
            "handle_revoked",
            handle=handle,
            pid=revocation.pid,
            resource_id=revocation.resource_id,
        )
        return revocation

    def notify(self, name: str, **payload: Any) -> None:
        if self._listener is not None:
            self._listener({"event": name, **payload})

    def _load_entity(
        self,
        pid: int,
        entity: ResourceEntity,
        grants: tuple[ResourceGrant, ...],
    ) -> None:
        handle = next(
            grant.handle
            for grant in grants
            if grant.resource_id == entity.resource_id
        )
        try:
            state = open_entity(entity.kind, entity.identity, self.loader)
        except BaseException as error:
            self.notify(
                "resource_load_failed",
                pid=pid,
                resource_id=entity.resource_id,
                error=str(error),
            )
            raise
        self.store.mark_loaded(entity.resource_id, state)
        self.notify(
            "resource_load_succeeded",
            pid=pid,
            resource_id=entity.resource_id,
            handle=handle,
            kind=kind_name(entity.kind),
        )

    def _take_release(self, pid: int) -> tuple[ResourceEntity, ...]:
        return tuple(self.store.release(pid))

    def _unload_all(self, unloaded: tuple[ResourceEntity, ...]) -> None:
        for entity in unloaded:
            self._unload_entity(entity)

    def _unload_entity(self, entity: ResourceEntity) -> None:
        close_entity(entity.kind, entity.identity, entity.state, self.loader)
        self.store.mark_unloaded(entity.resource_id)
        self.notify("resource_unloaded", resource_id=entity.resource_id)


def _grant_for(compiled: CompiledResource) -> ResourceGrant:
    return ResourceGrant(
        resource_id=compiled.resource_id,
        kind=compiled.kind,
        handle=secrets.token_hex(16),
        call_params=dict(compiled.call_params),
        share_mode=compiled.share_mode,
        metadata={
            "identity": dict(compiled.identity),
            "share_granted": compiled.share_granted,
        },
    )
