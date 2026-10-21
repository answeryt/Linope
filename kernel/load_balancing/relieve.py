"""Add one helper when calculated pressure says this process needs it."""

from __future__ import annotations

from typing import Any

from kernel.calculate.measure import Pressure


def relieve(
    book: Any,
    pid: int,
    pressure: Pressure,
    *,
    delegating: bool,
) -> int:
    """Raise ``worker_ceiling`` by one when pressure calls for it.

    There is no helper cap. Several reasons at once still add only one.
    """
    record = book.get(int(pid))
    if record is None:
        return 1
    room = dict(record.room)
    current = int(room.get("worker_ceiling") or 1)
    if pressure.activity == "closed" or not _needed(pressure, delegating=delegating):
        return current
    updated = current + 1
    room["worker_ceiling"] = updated
    record.room = room
    book.save()
    return updated


def _needed(pressure: Pressure, *, delegating: bool) -> bool:
    if pressure.context_full:
        return True
    if pressure.peers > 0 and pressure.activity == "with":
        return True
    return delegating and pressure.activity in {"self", "with"}
