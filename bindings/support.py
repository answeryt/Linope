"""Small pieces the transports share. The kernel does not import them."""

from __future__ import annotations

from typing import Any


def needs(package: str, module: str) -> Any:
    """Import a library a transport is built on, or say which package to install."""
    import importlib

    try:
        return importlib.import_module(module)
    except ImportError as exc:
        raise RuntimeError(f"这个通道要先安装 {package}: pip install {package}") from exc


class Inbox:
    """Received messages for one address, numbered as they arrive."""

    def __init__(self) -> None:
        import threading

        self._lock = threading.Lock()
        self._rows: list[dict[str, Any]] = []

    def put(self, message: dict[str, Any]) -> int:
        with self._lock:
            seq = len(self._rows) + 1
            self._rows.append({**message, "seq": seq})
            return seq

    def after(self, seq: int) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(row) for row in self._rows if row["seq"] > int(seq)]
