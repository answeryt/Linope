"""Process cleanup policy separated from the resource ledger."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from kernel.process.process_manager.liveness import process_matches


class ProcessReaper:
    """Apply an injected liveness check and cleanup operation."""

    def __init__(
        self,
        reap: Callable[[], None],
        *,
        is_alive: Callable[[int | None, str | None], bool] = process_matches,
    ) -> None:
        self._reap = reap
        self._is_alive = is_alive

    def reap_if_dead(self, row: dict[str, Any] | None) -> bool:
        if row is None or row.get("status") not in {"starting", "running"}:
            return False
        if self._is_alive(row.get("pid"), row.get("identity")):
            return False
        self._reap()
        return True
