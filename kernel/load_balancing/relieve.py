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
    """Open one more thread when pressure calls for it.

    Several reasons at once still add only one thread.
    """
    from kernel.thread.task import open_process_threads

    record = book.get(int(pid))
    if record is None:
        return 1
    table = open_process_threads(int(pid))
    current = len(table.threads())
    if pressure.activity == "closed" or not _needed(pressure, delegating=delegating):
        return current
    table.open()
    return len(table.threads())


def _needed(pressure: Pressure, *, delegating: bool) -> bool:
    """Context size does not add a worker. A full prompt is a memory decision."""

    if pressure.peers > 0 and pressure.activity == "with":
        return True
    return delegating and pressure.activity in {"self", "with"}
