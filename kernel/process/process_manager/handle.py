"""Client-only view of one peer Process."""

from __future__ import annotations

from typing import Any

from kernel.process.process_manager.client import Receipt


class ProcessHandle:
    """Delegate request operations without exposing a parent Process."""

    def __init__(self, process: Any) -> None:
        self._process = process

    @property
    def process_id(self) -> str:
        return str(self._process.activation.process_id)

    @property
    def pid(self) -> int | None:
        return self._process.pid

    @property
    def is_alive(self) -> bool:
        return bool(self._process.is_alive)

    def submit(self, message: dict[str, Any], **kwargs: Any) -> Receipt:
        return self._process.submit(message, **kwargs)

    def wait(self, receipt: Receipt, **kwargs: Any) -> dict[str, Any]:
        return self._process.wait(receipt, **kwargs)

    def send(self, message: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        return self._process.send(message, **kwargs)
