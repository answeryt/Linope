"""Protocols for the resource slice of the ledger."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from kernel.resource.context import ResourceContext
from kernel.resource.lease import HandleRevocation, ResourceEntity, ResourceLease
from kernel.resource.memory.page import Page
from kernel.resource.store.page_link import PageLink


class StoreIdentity(Protocol):
    locator: str
    path: Path | None


class LeaseStore(Protocol):
    def acquire(self, context: ResourceContext) -> tuple[ResourceLease, ...]:
        ...

    def release(self, process_id: str) -> tuple[ResourceEntity, ...]:
        ...

    def revoke(self, handle: str) -> HandleRevocation:
        ...

    def authorize(self, handle: str) -> None:
        ...

    def active_for(self, process_id: str) -> tuple[ResourceLease, ...]:
        ...

    def active_handles(self, process_id: str) -> tuple[str, ...]:
        ...

    def take_pending_loads(self, process_id: str) -> tuple[ResourceEntity, ...]:
        ...

    def mark_loaded(self, resource_id: str, state: dict[str, Any]) -> None:
        ...

    def mark_unloaded(self, resource_id: str) -> None:
        ...

    def entity(self, resource_id: str) -> ResourceEntity | None:
        ...


class PageStore(Protocol):
    def save_page(self, page: Page, link: PageLink) -> None:
        ...

    def link_at(self, handle: str) -> tuple[Page, PageLink] | None:
        ...

    def page_at(self, address: str) -> Page | None:
        ...


class PersistentStore(Protocol):
    def initialize_schema(self) -> None:
        ...

    def migrate(self) -> None:
        ...

    def check(self) -> dict[str, Any]:
        ...

    def close(self) -> None:
        ...
