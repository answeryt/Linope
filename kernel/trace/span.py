"""One recorded step. Export failure is a diagnostic, not a task failure."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from kernel.trace.context import TraceContext
from kernel.trace.exporter import Exporter, MemoryExporter

_EXPORTER: Exporter = MemoryExporter()


def set_exporter(exporter: Exporter) -> None:
    """Tests and deployments replace where spans go. The default keeps them in memory."""
    global _EXPORTER
    _EXPORTER = exporter


def current_exporter() -> Exporter:
    return _EXPORTER


@dataclass
class Span:
    """A causal step. Attributes must not carry secrets or full file contents."""

    name: str
    context: TraceContext
    attributes: dict[str, Any] = field(default_factory=dict)
    start: float = field(default_factory=time.time)
    end: float | None = None
    status: str = "ok"
    error_type: str = ""

    def set(self, **attributes: Any) -> None:
        self.attributes.update(attributes)

    def finish(self, *, status: str = "ok", error_type: str = "") -> dict[str, Any]:
        """Export the span. A broken exporter is reported and then ignored."""
        self.end = time.time()
        self.status = status
        self.error_type = error_type
        record = {
            "name": self.name,
            "trace_id": self.context.trace_id,
            "span_id": self.context.span_id,
            "parent_span_id": self.context.parent_span_id,
            "start": self.start,
            "end": self.end,
            "status": status,
            "attributes": dict(self.attributes),
        }
        if error_type:
            record["error.type"] = error_type
        try:
            _EXPORTER.export(record)
            record["exported"] = True
        except Exception as exc:
            record["exported"] = False
            record["export_error"] = type(exc).__name__
        return record
