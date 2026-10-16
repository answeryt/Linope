"""Where finished spans go. The task ledger does not wait for this."""

from __future__ import annotations

from typing import Any, Protocol


class Exporter(Protocol):
    def export(self, span: dict[str, Any]) -> None:
        """Accept one finished span. Raising must not change a task."""


class MemoryExporter:
    """Keep spans in this process so a test can read them."""

    def __init__(self) -> None:
        self.spans: list[dict[str, Any]] = []

    def export(self, span: dict[str, Any]) -> None:
        self.spans.append(dict(span))


class FailingExporter:
    """An exporter that always fails. Callers must keep working."""

    def export(self, span: dict[str, Any]) -> None:
        del span
        raise RuntimeError("追踪出口不可用")
