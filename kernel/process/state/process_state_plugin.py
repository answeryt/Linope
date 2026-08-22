# -*- coding: utf-8 -*-
"""Agent Process state names and legal transitions.

This is not an OS process state. Host injects ``transition`` into lifecycle
so that plugin never imports this file.
"""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from typing import Any


PLUGIN_NAME = "kernel_process_state"
PLUGIN_VERSION = "1.0"

NEW = "new"
READY = "ready"
RUNNING = "running"
WAITING = "waiting"
SUSPENDED = "suspended"
TERMINATED = "terminated"

PROCESS_STATES = (NEW, READY, RUNNING, WAITING, SUSPENDED, TERMINATED)

TRANSITIONS: dict[str, frozenset[str]] = {
    NEW: frozenset({READY, RUNNING, TERMINATED}),
    READY: frozenset({RUNNING, TERMINATED}),
    RUNNING: frozenset({WAITING, SUSPENDED, READY, TERMINATED}),
    WAITING: frozenset({READY, RUNNING, TERMINATED}),
    SUSPENDED: frozenset({READY, RUNNING, TERMINATED}),
    TERMINATED: frozenset(),
}


class InvalidProcessState(ValueError):
    """Raised when a process state change is not allowed."""


def can_transition(current: str | None, target: str) -> bool:
    if target not in PROCESS_STATES:
        return False
    if current is None:
        return target == NEW
    allowed = TRANSITIONS.get(str(current))
    return bool(allowed and target in allowed)


def transition(
    record: Mapping[str, Any],
    target: str,
    *,
    reason: str | None = None,
) -> dict[str, Any]:
    """Return an updated copy. Does not mutate ``record``."""
    current = record.get("state")
    current_text = None if current is None else str(current)
    if not can_transition(current_text, target):
        raise InvalidProcessState(f"{current_text!r} -> {target!r}")
    updated: MutableMapping[str, Any] = dict(record)
    updated["state"] = target
    if reason is not None:
        updated["wait_reason"] = reason
    elif target in {READY, RUNNING, TERMINATED}:
        updated.pop("wait_reason", None)
    return dict(updated)
