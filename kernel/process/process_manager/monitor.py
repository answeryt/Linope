"""Flat Process monitor facade."""

from __future__ import annotations

from typing import Any

from kernel.process.process_manager.handle import ProcessHandle
from kernel.process.process_manager.reaper import ProcessReaper


class ProcessMonitor:
    """Observe and control peers without parent/child ownership."""

    def __init__(self, *, reap: Any | None = None) -> None:
        self._reaper = ProcessReaper(reap) if reap is not None else None

    def handle(self, process: Any) -> ProcessHandle:
        return ProcessHandle(process)

    def stop(self, process: Any, timeout: float | None = None) -> None:
        process.stop(timeout)

    def reap_if_dead(self, process: Any) -> bool:
        if self._reaper is None:
            return False
        return self._reaper.reap_if_dead(process._row())
