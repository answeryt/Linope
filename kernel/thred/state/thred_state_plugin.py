# -*- coding: utf-8 -*-
"""Agent Thread states. This is not an OS thread.

Logical execution context: ready / running / waiting / done. Host injects
``transition`` into lifecycle so siblings never import this file.
"""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from typing import Any


PLUGIN_NAME = "kernel_thred_state"
PLUGIN_VERSION = "1.0"

READY = "ready"
RUNNING = "running"
WAITING = "waiting"
SUSPENDED = "suspended"
DONE = "done"
FAILED = "failed"
CANCELLED = "cancelled"

THREAD_STATES = (READY, RUNNING, WAITING, SUSPENDED, DONE, FAILED, CANCELLED)

TRANSITIONS: dict[str, frozenset[str]] = {
    READY: frozenset({RUNNING, CANCELLED}),
    RUNNING: frozenset({WAITING, SUSPENDED, READY, DONE, FAILED, CANCELLED}),
    WAITING: frozenset({READY, RUNNING, CANCELLED, FAILED}),
    SUSPENDED: frozenset({READY, RUNNING, CANCELLED}),
    DONE: frozenset(),
    FAILED: frozenset(),
    CANCELLED: frozenset(),
}


class InvalidThreadState(ValueError):
    """Raised when a thread state change is not allowed."""


def can_transition(current: str | None, target: str) -> bool:
    if target not in THREAD_STATES:
        return False
    if current is None:
        return target == READY
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
        raise InvalidThreadState(f"{current_text!r} -> {target!r}")
    updated: MutableMapping[str, Any] = dict(record)
    updated["state"] = target
    if reason is not None:
        updated["wait_reason"] = reason
    elif target in {READY, RUNNING, DONE, FAILED, CANCELLED}:
        updated.pop("wait_reason", None)
    return dict(updated)
