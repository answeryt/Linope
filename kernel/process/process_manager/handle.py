"""Client-only view of one peer Process."""

from __future__ import annotations

from typing import Any


class ProcessHandle:
    """The activation identity of one peer process."""

    def __init__(self, process: Any) -> None:
        self._process = process

    @property
    def pid(self) -> int:
        return int(self._process.activation.pid)
