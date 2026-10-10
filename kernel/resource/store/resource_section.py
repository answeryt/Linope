"""Resource entities, leases, handles, and long-term pages."""

from __future__ import annotations

import threading
from typing import Any

from kernel.resource.context import ResourceContext
from kernel.resource.lease import (
    HandleRevocation,
    HandleStatus,
    LeaseStatus,
    ResourceEntity,
    ResourceLease,
    ResourceLeaseManager,
)
from kernel.resource.memory.page import Page, PageState
from kernel.resource.store.page_link import PageLink, page_link_from


class ResourceSection:
    """The resource slice of a ledger. It does not record process rows."""

    name = "resource"
    flat_keys = ("entities", "leases", "handles", "pending_loads", "pages")

    def __init__(self, lock: threading.RLock) -> None:
        self._lock = lock
        self._manager = ResourceLeaseManager()
        self._pages: dict[str, tuple[Page, PageLink]] = {}

    def acquire(self, context: ResourceContext) -> tuple[ResourceLease, ...]:
        with self._lock:
            return self._manager.acquire(context)

    def release(self, process_id: str) -> tuple[ResourceEntity, ...]:
        with self._lock:
            return self._manager.release(process_id)

    def revoke(self, handle: str) -> HandleRevocation:
        with self._lock:
            return self._manager.revoke(handle)

    def authorize(self, handle: str) -> None:
        with self._lock:
            self._manager.authorize(handle)

    def active_for(self, process_id: str) -> tuple[ResourceLease, ...]:
        with self._lock:
            return self._manager.active_for(process_id)

    def active_handles(self, process_id: str) -> tuple[str, ...]:
        with self._lock:
            return tuple(
                str(handle)
                for handle, record in self._manager._handles.items()
                if record["process_id"] == process_id
                and record["status"] == HandleStatus.ACTIVE
            )

    def take_pending_loads(self, process_id: str) -> tuple[ResourceEntity, ...]:
        with self._lock:
            return self._manager.take_pending_loads(process_id)

    def mark_loaded(self, resource_id: str, state: dict[str, Any]) -> None:
        with self._lock:
            self._manager.mark_loaded(resource_id, state)

    def mark_unloaded(self, resource_id: str) -> None:
        with self._lock:
            self._manager.mark_unloaded(resource_id)

    def entity(self, resource_id: str) -> ResourceEntity | None:
        with self._lock:
            return self._manager.entity(resource_id)

    def save_page(self, page: Page, link: object) -> None:
        with self._lock:
            self._pages[page.address] = (page, page_link_from(link))

    def link_at(self, handle: str) -> tuple[Page, PageLink] | None:
        if not handle:
            return None
        with self._lock:
            for page, link in self._pages.values():
                if link.handle == handle:
                    return page, link
        return None

    def page_at(self, address: str) -> Page | None:
        with self._lock:
            found = self._pages.get(address)
            return None if found is None else found[0]

    def active_lease_rows(
        self,
    ) -> tuple[tuple[str, ResourceEntity, ResourceLease, str], ...]:
        """Active leases plus the handle that points at each one."""
        with self._lock:
            rows: list[tuple[str, ResourceEntity, ResourceLease, str]] = []
            for resource_id, leases in self._manager._leases.items():
                entity = self._manager._entities.get(resource_id)
                if entity is None:
                    continue
                for lease in leases:
                    if lease.status != LeaseStatus.ACTIVE:
                        continue
                    rows.append(
                        (
                            resource_id,
                            entity,
                            lease,
                            _handle_for(
                                self._manager._handles,
                                lease.process_id,
                                resource_id,
                            ),
                        )
                    )
            return tuple(rows)

    def window_used(self, resource_id: str) -> int:
        with self._lock:
            used = 0
            for page, _link in self._pages.values():
                if page.address == resource_id and page.occupies_window():
                    used += page.size
            return used

    def export_part(self) -> dict[str, Any]:
        manager = self._manager
        return {
            "entities": {
                resource_id: {
                    "resource_id": entity.resource_id,
                    "kind": entity.kind,
                    "identity": entity.identity,
                    "status": entity.status,
                    "refcount": entity.refcount,
                    "fencing_token": entity.fencing_token,
                    "state": entity.state,
                }
                for resource_id, entity in manager._entities.items()
            },
            "leases": {
                resource_id: [
                    {
                        "lease_id": lease.lease_id,
                        "process_id": lease.process_id,
                        "resource_id": lease.resource_id,
                        "status": lease.status.value,
                        "fencing_token": lease.fencing_token,
                        "share_mode": lease.share_mode.value,
                    }
                    for lease in leases
                ]
                for resource_id, leases in manager._leases.items()
            },
            "handles": {
                handle: {
                    key: (
                        value.value
                        if isinstance(value, (HandleStatus, LeaseStatus))
                        else value
                    )
                    for key, value in record.items()
                }
                for handle, record in manager._handles.items()
            },
            "pending_loads": {
                process_id: list(resource_ids)
                for process_id, resource_ids in manager._pending_loads.items()
            },
            "pages": {
                address: {
                    "page": {
                        "address": page.address,
                        "size": page.size,
                        "state": page.state.value,
                    },
                    "link": {
                        "relation": link.relation,
                        "resource_id": link.resource_id,
                        "handle": link.handle,
                    },
                }
                for address, (page, link) in self._pages.items()
            },
        }

    def import_part(self, payload: dict[str, Any]) -> None:
        from kernel.resource.definition import ResourceShareMode

        manager = self._manager
        manager._entities.clear()
        manager._leases.clear()
        manager._handles.clear()
        manager._pending_loads.clear()
        self._pages.clear()
        for resource_id, raw in (payload.get("entities") or {}).items():
            manager._entities[str(resource_id)] = ResourceEntity(
                resource_id=str(raw.get("resource_id", resource_id)),
                kind=str(raw.get("kind", "")),
                identity=dict(raw.get("identity") or {}),
                status=str(raw.get("status", "unloaded")),
                refcount=int(raw.get("refcount", 0)),
                fencing_token=int(raw.get("fencing_token", 0)),
                state=(
                    dict(raw["state"]) if isinstance(raw.get("state"), dict) else None
                ),
            )
        for resource_id, raw_leases in (payload.get("leases") or {}).items():
            manager._leases[str(resource_id)] = [
                ResourceLease(
                    lease_id=str(raw["lease_id"]),
                    process_id=str(raw["process_id"]),
                    resource_id=str(raw.get("resource_id", resource_id)),
                    status=LeaseStatus(str(raw.get("status", "active"))),
                    fencing_token=int(raw.get("fencing_token", 0)),
                    share_mode=ResourceShareMode(str(raw["share_mode"])),
                )
                for raw in raw_leases
            ]
        for handle, raw in (payload.get("handles") or {}).items():
            manager._handles[str(handle)] = dict(raw)
        manager._pending_loads.update(
            {
                str(key): [str(item) for item in value]
                for key, value in (payload.get("pending_loads") or {}).items()
            }
        )
        for address, raw in (payload.get("pages") or {}).items():
            raw_page = raw["page"]
            raw_link = raw["link"]
            self._pages[str(address)] = (
                Page(
                    address=str(raw_page["address"]),
                    size=int(raw_page["size"]),
                    state=PageState(str(raw_page["state"])),
                ),
                PageLink(
                    relation=str(raw_link["relation"]),
                    resource_id=str(raw_link["resource_id"]),
                    handle=str(raw_link.get("handle", "")),
                ),
            )


def _handle_for(
    handles: dict[str, dict[str, Any]],
    process_id: str,
    resource_id: str,
) -> str:
    for record in handles.values():
        if (
            record.get("process_id") == process_id
            and record.get("resource_id") == resource_id
            and record.get("status") == HandleStatus.ACTIVE
        ):
            return str(record.get("handle") or "")
    return ""
