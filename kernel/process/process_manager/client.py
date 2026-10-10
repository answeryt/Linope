"""Request-client primitives for managed capability processes."""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any


@dataclass
class Receipt:
    """A request ticket that does not retain the process supervisor."""

    request_id: str
    process_id: str
    _lookup: Callable[[str], dict[str, Any] | None]
    _wait: Callable[..., dict[str, Any]]

    def ready(self) -> bool:
        row = self._lookup(self.request_id)
        return row is not None and row["status"] == "done" and row["reply"] is not None

    def wait(
        self,
        timeout: float = 10.0,
        *,
        caller_id: str | None = None,
    ) -> dict[str, Any]:
        return self._wait(self, timeout, caller_id=caller_id)


def wait_first(
    receipts: Sequence[Receipt],
    timeout: float = 10.0,
) -> tuple[Receipt, ...]:
    """Return receipts that have completed, or the first batch to arrive."""
    deadline = time.monotonic() + timeout
    while True:
        ready = tuple(item for item in receipts if item.ready())
        if ready or time.monotonic() >= deadline:
            return ready
        time.sleep(0.02)
