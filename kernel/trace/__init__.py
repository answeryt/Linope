"""Optional diagnostics, plus the activity trail of capability processes."""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from typing import Any

from kernel.trace.activity import ActivityLog


@dataclass(frozen=True)
class Diagnostic:
    trace_id: str
    error: str = ""
    location: str = ""
    details: dict[str, Any] | None = None


def new_trace_id() -> str:
    return secrets.token_hex(16)


def record_error(error: BaseException | str, *, location: str = "") -> Diagnostic:
    return Diagnostic(
        trace_id=new_trace_id(),
        error=str(error),
        location=location,
    )


__all__ = ["ActivityLog", "Diagnostic", "new_trace_id", "record_error"]
