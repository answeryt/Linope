"""Neutral facts exchanged between the kernel and a host adapter.

This module defines data and ownership, not terminal presentation. A host may
render these facts as a TUI, a headless response, or another interface.
"""

from __future__ import annotations

from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from typing import Any, Protocol

PROTOCOL_VERSION = 1


@dataclass(frozen=True)
class CommandError:
    """A command failure that a host can render or serialize."""

    code: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)

    def to_payload(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "details": dict(self.details),
        }


@dataclass(frozen=True)
class CommandResult:
    """The structured value or error produced by one command."""

    value: Any = None
    error: CommandError | None = None

    @property
    def ok(self) -> bool:
        return self.error is None

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"ok": self.ok}
        if self.error is None:
            payload["value"] = self.value
        else:
            payload["error"] = self.error.to_payload()
        return payload


@dataclass(frozen=True)
class KernelEvent:
    """One versioned, correlated kernel fact."""

    kind: str
    data: dict[str, Any] = field(default_factory=dict)
    request_id: str = ""
    turn_id: str = ""
    pid: int | None = None
    seq: int = 0

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "version": PROTOCOL_VERSION,
            "kind": self.kind,
            "seq": self.seq,
            "data": dict(self.data),
        }
        if self.request_id:
            payload["request_id"] = self.request_id
        if self.turn_id:
            payload["turn_id"] = self.turn_id
        if self.pid is not None:
            payload["pid"] = self.pid
        return payload


class EventSink(Protocol):
    """A receiver of kernel facts."""

    def emit(self, event: KernelEvent) -> None:
        """Accept one event in sequence order."""


_sink: ContextVar[EventSink | None] = ContextVar("linope_event_sink", default=None)


def current_event_sink() -> EventSink:
    """Return the host sink for the current command context."""

    found = _sink.get()
    return found if found is not None else NullEventSink()


def bind_event_sink(sink: EventSink) -> Token[EventSink | None]:
    """Bind one host sink to the current command context."""

    return _sink.set(sink)


def reset_event_sink(token: Token[EventSink | None]) -> None:
    """Restore the previous host sink."""

    _sink.reset(token)


class NullEventSink:
    """Discard events for callers that only need the returned value."""

    def emit(self, event: KernelEvent) -> None:
        del event


class CollectingEventSink:
    """Keep emitted facts for tests and in-process host adapters."""

    def __init__(self) -> None:
        self.events: list[KernelEvent] = []

    def emit(self, event: KernelEvent) -> None:
        self.events.append(event)
