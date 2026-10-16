"""Kind-routed resource pool: leases, refcounted entities, and handles."""

from __future__ import annotations

import secrets
import threading
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any, Protocol

from kernel.resource.compile import CompiledResource
from kernel.resource.handle_view import ResourceContext
from kernel.resource.definition import ResourceGrant, ResourceKind
from kernel.resource.lease import HandleRevocation, ResourceEntity

PoolListener = Callable[[dict[str, Any]], None]


class ResourcePoolStore(Protocol):
    """Lease slice required by the resource pool.

    Process rows live on the process ledger. The pool only acquires, loads,
    and releases resource entities.
    """

    def acquire(self, context: ResourceContext) -> Any:
        ...

    def take_pending_loads(self, process_id: str) -> tuple[ResourceEntity, ...]:
        ...

    def release(self, process_id: str) -> tuple[ResourceEntity, ...]:
        ...

    def authorize(self, handle: str, process_id: str) -> None:
        ...

    def revoke(self, handle: str) -> HandleRevocation:
        ...

    def mark_loaded(self, resource_id: str, state: dict[str, Any]) -> None:
        ...

    def mark_unloaded(self, resource_id: str) -> None:
        ...


class RecordingLoader:
    """Remember that an entity is loaded without fetching real weights or tools."""

    def load(self, kind: ResourceKind, identity: dict[str, Any]) -> dict[str, Any]:
        return {
            "loaded": True,
            "kind": kind.value,
            "identity": dict(identity),
        }

    def unload(
        self,
        kind: ResourceKind,
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
        self._grants_for_process: dict[str, tuple[ResourceGrant, ...]] = {}

    def bind(
        self,
        process_id: str,
        capability_id: str,
        compiled: tuple[CompiledResource, ...],
    ) -> tuple[ResourceGrant, ...]:
        grants = tuple(_grant_for(item) for item in compiled)
        context = ResourceContext(
            process_id=process_id,
            capability_id=capability_id,
            grants=grants,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        error: BaseException | None = None
        with self._lock:
            try:
                self.store.acquire(context)
                self._grants_for_process[process_id] = grants
                pending = self.store.take_pending_loads(process_id)
            except BaseException as exc:
                unloaded = self._take_release(process_id)
                error = exc
            else:
                unloaded = ()
        if error is not None:
            self._unload_all(unloaded)
            raise error
        try:
            for entity in pending:
                self._load_entity(process_id, entity, grants)
        except BaseException:
            with self._lock:
                unloaded = self._take_release(process_id)
            self._unload_all(unloaded)
            raise
        return grants

    def grants_for(self, process_id: str) -> tuple[ResourceGrant, ...]:
        return self._grants_for_process[process_id]

    def release(self, process_id: str) -> tuple[ResourceEntity, ...]:
        with self._lock:
            unloaded = self._take_release(process_id)
        self._unload_all(unloaded)
        return unloaded

    def authorize(self, handle: str, process_id: str) -> None:
        """Check that this process still holds the handle."""
        with self._lock:
            self.store.authorize(handle, process_id)

    def revoke(self, handle: str) -> HandleRevocation:
        with self._lock:
            revocation = self.store.revoke(handle)
        self._unload_all(revocation.unloaded)
        self.notify(
            "handle_revoked",
            handle=handle,
            process_id=revocation.process_id,
            resource_id=revocation.resource_id,
        )
        return revocation

    def notify(self, name: str, **payload: Any) -> None:
        if self._listener is not None:
            self._listener({"event": name, **payload})

    def _load_entity(
        self,
        process_id: str,
        entity: ResourceEntity,
        grants: tuple[ResourceGrant, ...],
    ) -> None:
        kind = ResourceKind(entity.kind)
        handle = next(
            grant.handle
            for grant in grants
            if grant.resource_id == entity.resource_id
        )
        try:
            state = self.loader.load(kind, entity.identity)
        except BaseException as error:
            self.notify(
                "resource_load_failed",
                process_id=process_id,
                resource_id=entity.resource_id,
                error=str(error),
            )
            raise
        self.store.mark_loaded(entity.resource_id, state)
        self.notify(
            "resource_load_succeeded",
            process_id=process_id,
            resource_id=entity.resource_id,
            handle=handle,
            kind=entity.kind,
        )

    def _take_release(self, process_id: str) -> tuple[ResourceEntity, ...]:
        return tuple(self.store.release(process_id))

    def _unload_all(self, unloaded: tuple[ResourceEntity, ...]) -> None:
        for entity in unloaded:
            self._unload_entity(entity)

    def _unload_entity(self, entity: ResourceEntity) -> None:
        try:
            kind = ResourceKind(entity.kind)
        except ValueError:
            self.store.mark_unloaded(entity.resource_id)
            return
        self.loader.unload(
            kind,
            entity.identity,
            entity.state,
        )
        self.store.mark_unloaded(entity.resource_id)
        self.notify("resource_unloaded", resource_id=entity.resource_id)


def _grant_for(compiled: CompiledResource) -> ResourceGrant:
    return ResourceGrant(
        resource_id=compiled.resource_id,
        kind=compiled.kind,
        handle=secrets.token_hex(16),
        limits=dict(compiled.limits),
        call_params=dict(compiled.call_params),
        share_mode=compiled.share_mode,
        metadata={
            "identity": dict(compiled.identity),
            "share_granted": compiled.share_granted,
        },
    )
