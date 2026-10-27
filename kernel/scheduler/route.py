"""Send one request to a resource, then through a channel to one peer process.

The caller names a resource kind and identity. This module does not take a
lease. A new process, when one is required, is started by the opener the
caller supplies, which should be the existing reconciler.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from kernel.load_balancing.hints import Seat, one_resource, seats
from kernel.load_balancing.pick import choose
from kernel.load_balancing.process_scale import close_idle, open_peer
from kernel.load_balancing.workers import raise_on_process


def route(
    store: Any,
    *,
    kind: str,
    identity: dict[str, Any],
    body: dict[str, Any],
    capability: str,
    opener: Callable[[], str],
    thread_safe: bool = False,
    max_processes: int = 4,
    max_threads: int = 4,
    sender_id: str | None = None,
    channel: Any = None,
) -> str:
    """Hand ``body`` to a peer process that holds this resource, through ``channel``."""

    if channel is None:
        raise ValueError("No channel selected")
    if max_processes < 1:
        raise ValueError("Process limit must be at least 1")
    existing = str(body.get("request_id") or "")
    if _scheduled_body(body):
        if not existing:
            raise RuntimeError("Nothing is reserved; cannot place")
        row = store.lookup_request(existing)
        if row is None or row.get("status") != "reserved":
            raise RuntimeError("The reservation is gone; cannot place")
    found = one_resource(seats(store, kind, identity))
    chosen = choose(found)
    if chosen is None and not found:
        process_id = open_peer(opener, current=0, ceiling=max_processes)
    elif chosen is not None:
        process_id = chosen.process_id
    else:
        process_id = _make_room(
            store,
            found,
            capability=capability,
            opener=opener,
            thread_safe=thread_safe,
            max_processes=max_processes,
            max_threads=max_threads,
        )
    close_idle(store, found, floor=1, keep=process_id)
    if existing and callable(getattr(store, "place_request", None)):
        if not store.place_request(existing, process_id):
            raise RuntimeError("The reservation is gone; cannot place")
        return existing
    return channel.send(str(process_id), dict(body), sender_id or "")


def _scheduled_body(body: dict[str, Any]) -> bool:
    return any(body.get(key) not in (None, "") for key in ("lane", "depends_on", "service_key", "start_by"))


def _make_room(
    store: Any,
    found: tuple[Seat, ...],
    *,
    capability: str,
    opener: Callable[[], str],
    thread_safe: bool,
    max_processes: int,
    max_threads: int,
) -> str:
    host = min(
        found,
        key=lambda seat: (seat.claimed, seat.pending, seat.rtt_ms, seat.process_id),
    )
    if thread_safe and not host.budget_full and host.capacity < max_threads:
        raise_on_process(store, host.process_id, 1, max_threads)
        return host.process_id
    if not store.shares_capability(capability):
        raise ValueError("Sharing was not named; cannot open another copy to split the load")
    return open_peer(opener, current=len(found), ceiling=max_processes)
