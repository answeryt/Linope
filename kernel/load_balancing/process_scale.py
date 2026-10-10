"""Open or stop peer processes. Starting still goes through the reconciler.

The compare step follows Celery's worker/autoscale.py: more waiting work than
running processes means open one more, and never pass the ceiling. Stopping
follows billiard/pool.py shrink: only an idle process is asked to stop.
https://github.com/celery/celery/blob/main/celery/worker/autoscale.py
https://github.com/celery/billiard/blob/main/billiard/pool.py
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from kernel.load_balancing.hints import Seat


def reconciler_opener(reconciler: Any, declaration: Any, thread_policy: Any = None) -> Callable[[], str]:
    """Open one peer through the existing reconciler and return its process id."""

    def open_one() -> str:
        process = reconciler.start(declaration, thread_policy=thread_policy)
        return str(process.activation.process_id)

    return open_one


def open_peer(opener: Callable[[], str], *, current: int, ceiling: int) -> str:
    """Start one more peer process and return its process id."""
    if ceiling < 1:
        raise ValueError("进程上限至少为 1")
    if current >= ceiling:
        raise ValueError("进程已经到上限")
    return opener()


def close_idle(
    store: Any,
    found: tuple[Seat, ...],
    *,
    floor: int,
    keep: str | None = None,
) -> tuple[str, ...]:
    """Ask idle processes to stop, leaving at least ``floor`` of them."""
    if floor < 0:
        raise ValueError("最少进程数不能是负数")
    idle = [
        seat
        for seat in found
        if seat.process_id != keep and seat.pending == 0 and seat.claimed == 0
    ]
    can_close = max(0, len(found) - floor)
    closed: list[str] = []
    for seat in idle:
        if can_close <= 0:
            break
        store.set_desired(seat.process_id, "stop")
        closed.append(seat.process_id)
        can_close -= 1
    return tuple(closed)
