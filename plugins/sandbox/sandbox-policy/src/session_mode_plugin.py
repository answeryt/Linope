# -*- coding: utf-8 -*-
"""Per-session sandbox mode: the log is the store.

effective = last sandbox/mode event, or None so callers apply the deployment
default. set_sandbox_mode appends exactly one event. This file never imports
sibling plugins.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


PLUGIN_NAME = "sandbox_session_mode"
PLUGIN_VERSION = "1.0"

READ_ONLY = "read-only"
WORKSPACE_WRITE = "workspace-write"
DANGER_FULL_ACCESS = "danger-full-access"

SANDBOX_MODES: tuple[str, ...] = (READ_ONLY, WORKSPACE_WRITE, DANGER_FULL_ACCESS)
MODE_EVENT = "sandbox/mode"


def require_sandbox_mode(mode: str) -> str:
    text = str(mode)
    if text not in SANDBOX_MODES:
        raise ValueError(f"sandbox/mode carries unknown mode {text!r}")
    return text


def effective_sandbox_mode(events: Sequence[Any]) -> str | None:
    """Last sandbox/mode in log order, or None when the session never switched."""
    for event in reversed(events):
        if _event_type(event) != MODE_EVENT:
            continue
        mode = _event_mode(event)
        if mode is None:
            return None
        return require_sandbox_mode(mode)
    return None


def set_sandbox_mode(session: Any, mode: str) -> None:
    """The switch is its event. Nothing mutates mode out of band."""
    payload = {"mode": require_sandbox_mode(mode)}
    append = getattr(session, "append", None)
    if callable(append):
        append(MODE_EVENT, payload)
        return
    events = getattr(session, "events", None)
    if isinstance(events, list):
        events.append({"type": MODE_EVENT, "data": payload})
        return
    raise TypeError("session must provide append or a mutable events list")


def validate_mode_event(event: Any) -> None:
    """Reject a forged durable sandbox/mode; ignore other event types."""
    if _event_type(event) != MODE_EVENT:
        return
    mode = _event_mode(event)
    if mode is None:
        raise ValueError("sandbox/mode carries unknown mode None")
    require_sandbox_mode(mode)


def _event_type(event: Any) -> str:
    if isinstance(event, Mapping):
        return str(event.get("type") or "")
    return str(getattr(event, "type", "") or "")


def _event_mode(event: Any) -> str | None:
    data = event.get("data") if isinstance(event, Mapping) else getattr(event, "data", None)
    if isinstance(data, Mapping):
        mode = data.get("mode")
        return None if mode is None else str(mode)
    mode = getattr(data, "mode", None) if data is not None else None
    return None if mode is None else str(mode)
