"""W3C trace context carried beside an Agent task. It is not the task itself."""

from __future__ import annotations

import secrets
from dataclasses import dataclass


@dataclass(frozen=True)
class TraceContext:
    """One position in a trace. ``trace_id`` is the whole graph; ``span_id`` is this step."""

    trace_id: str
    span_id: str
    parent_span_id: str = ""
    sampled: bool = True

    def child(self) -> "TraceContext":
        """A new span under this one. The trace id stays."""
        return TraceContext(
            trace_id=self.trace_id,
            span_id=new_span_id(),
            parent_span_id=self.span_id,
            sampled=self.sampled,
        )

    def traceparent(self) -> str:
        """The ``traceparent`` value other processes copy onto their envelopes."""
        flags = "01" if self.sampled else "00"
        return f"00-{self.trace_id}-{self.span_id}-{flags}"


def new_trace_id() -> str:
    """16 random bytes, hex. All zeroes is not produced."""
    return secrets.token_hex(16)


def new_span_id() -> str:
    """8 random bytes, hex."""
    return secrets.token_hex(8)


def root_context(*, sampled: bool = True) -> TraceContext:
    return TraceContext(trace_id=new_trace_id(), span_id=new_span_id(), sampled=sampled)


def parse_traceparent(value: str) -> TraceContext:
    """Read one ``traceparent`` header. A bad value is rejected, not repaired."""
    parts = value.strip().split("-")
    if len(parts) != 4 or parts[0] != "00":
        raise ValueError("traceparent 格式不对")
    trace_id, span_id, flags = parts[1], parts[2], parts[3]
    if len(trace_id) != 32 or len(span_id) != 16 or len(flags) != 2:
        raise ValueError("traceparent 长度不对")
    if trace_id == "0" * 32 or span_id == "0" * 16:
        raise ValueError("traceparent 不能是全零")
    if any(char not in "0123456789abcdef" for char in trace_id + span_id + flags):
        raise ValueError("traceparent 只能使用小写十六进制")
    return TraceContext(
        trace_id=trace_id,
        span_id=span_id,
        sampled=flags == "01",
    )
