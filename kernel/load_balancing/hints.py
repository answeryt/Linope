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
    occupied: int
    window: int | None
    share_mode: str
    handle: str
    rtt_ms: int = 0

    @property
    def budget_full(self) -> bool:
        """The context window is full when occupancy is past the model's ceiling."""
        return self.window is not None and self.occupied > self.window

    @property
    def has_room(self) -> bool:
        return (not self.budget_full) and self.claimed < self.capacity


def seats(store: Any, kind: str, identity: dict[str, Any]) -> tuple[Seat, ...]:
    """List peer processes for one leased resource, or one capability name.

    An empty kind groups running processes of ``identity["capability"]``.
    That is how model processes are seated after the model lease is gone.
    """
    if not kind:
        raw = store.capability_seats(str(identity.get("capability") or ""))
    else:
        raw = store.resource_seats(kind, dict(identity))
    return tuple(Seat(**item) for item in raw)


def one_resource(found: tuple[Seat, ...]) -> tuple[Seat, ...]:
    """Peers are holders of one resource id. Separate copies are not a pool."""
    if not found:
        return ()
    resource_ids = {item.resource_id for item in found}
    if len(resource_ids) != 1:
        raise ValueError("These processes do not share one resource and cannot split work")
    return found
