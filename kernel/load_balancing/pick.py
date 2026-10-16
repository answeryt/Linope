"""Pick the peer process with more room.

Rewritten from lafikl/liblb p2c/p2c.go (MIT): look at two at random and keep
the less busy one. When only one or two are open, look at all of them, the
same idea as liblb bounded/bounded.go.
https://github.com/lafikl/liblb/blob/master/p2c/p2c.go
https://github.com/lafikl/liblb/blob/master/bounded/bounded.go
"""

from __future__ import annotations

import random
from collections.abc import Sequence

from kernel.load_balancing.hints import Seat


def choose(candidates: Sequence[Seat]) -> Seat | None:
    """Return a process that still has room, or nothing if every one is full."""
    open_seats = [seat for seat in candidates if seat.has_room]
    if not open_seats:
        return None
    if len(open_seats) <= 2:
        return min(open_seats, key=load_key)
    left, right = random.sample(open_seats, 2)
    if load_key(left) <= load_key(right):
        return left
    return right


def load_key(seat: Seat) -> tuple[int, int, int, str]:
    """Busy work, then round trip, then process id. A larger key is heavier."""
    return (seat.claimed, seat.pending, int(getattr(seat, "rtt_ms", 0) or 0), seat.process_id)
