"""Read the ledger hints that say which peer process still has room.

This does not keep a second busy table. It only reads leases, limits,
context pages, and the mailbox.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Seat:
    """One peer process that still holds a lease on a resource."""

    process_id: str
    resource_id: str
    capability_id: str
    kind: str
    identity: dict[str, Any]
    pending: int
    claimed: int
    limits: dict[str, Any]
    capacity: int
    window: int | None
    used: int
    share_mode: str
    handle: str

    @property
    def window_full(self) -> bool:
        return self.window is not None and self.used > self.window

    @property
    def has_room(self) -> bool:
        return (not self.window_full) and self.claimed < self.capacity


def seats(store: Any, kind: str, identity: dict[str, Any]) -> tuple[Seat, ...]:
    """List the processes that still lease this kind and identity."""
    raw = store.resource_seats(kind, dict(identity))
    return tuple(Seat(**item) for item in raw)


def one_resource(found: tuple[Seat, ...]) -> tuple[Seat, ...]:
    """Peers are holders of one resource id. Separate copies are not a pool."""
    if not found:
        return ()
    resource_ids = {item.resource_id for item in found}
    if len(resource_ids) != 1:
        raise ValueError("这些进程没有共用同一份资源，不能互相分单")
    return found
