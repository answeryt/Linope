"""Open or stop peer processes. Starting still goes through the reconciler."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from kernel.load_balancing.hints import Seat
from kernel.load_balancing.pick import load_key


def reconciler_opener(reconciler: Any, declaration: Any, thread_policy: Any = None) -> Callable[[], str]:
    """Open one peer through the existing reconciler and return its process id."""

    def open_one() -> str:
        process = reconciler.start(declaration, thread_policy=thread_policy)
        return str(process.activation.process_id)

    return open_one


def open_peer(opener: Callable[[], str], *, current: int, ceiling: int) -> str:
    """Start one more peer process and return its process id."""
    if ceiling < 1:
        raise ValueError("Process limit must be at least 1")
    if current >= ceiling:
        raise ValueError("Process count is already at the limit")
    return opener()


def close_idle(
    store: Any,
    found: tuple[Seat, ...],
    *,
    floor: int,
    keep: str | None = None,
) -> tuple[str, ...]:
    """Ask idle processes to stop, leaving at least ``floor`` of them.

    Heavier idle processes stop first. Weight is the same key ``choose`` uses:
    claimed work, waiting work, round trip, then process id.
    """
    if floor < 0:
        raise ValueError("Minimum process count cannot be negative")
    idle = [
        seat
        for seat in found
        if seat.process_id != keep and seat.pending == 0 and seat.claimed == 0
    ]
    idle.sort(key=load_key, reverse=True)
    can_close = max(0, len(found) - floor)
    closed: list[str] = []
    services_for = getattr(store, "services_for_process", None)
    for seat in idle:
        if can_close <= 0:
            break
        if callable(services_for) and services_for(seat.process_id):
            continue
        store.set_desired(seat.process_id, "stop")
        closed.append(seat.process_id)
        can_close -= 1
    return tuple(closed)
