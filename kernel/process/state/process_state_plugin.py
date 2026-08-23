# -*- coding: utf-8 -*-
"""Logical Process state names and legal transitions.

This is not an OS process state. Host injects ``transition`` into lifecycle
so that plugin never imports this file.
"""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


PLUGIN_NAME = "kernel_process_state"
PLUGIN_VERSION = "1.0"

NEW = "new"
READY = "ready"
RUNNING = "running"
WAITING = "waiting"
SUSPENDED = "suspended"
TERMINATED = "terminated"

PROCESS_STATES = (NEW, READY, RUNNING, WAITING, SUSPENDED, TERMINATED)
TERMINAL_STATES = frozenset({TERMINATED})

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


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_process_id() -> str:
    """Return an opaque ID for one durable Process identity."""
    return uuid4().hex


def new_run_id() -> str:
    """Return an opaque ID for one execution run of a Process."""
    return uuid4().hex


def build_process_run(
    process_type: str,
    *,
    process_id: str | None = None,
    run_id: str | None = None,
    definition_version: str = "1",
    state: str = NEW,
    pending_activations: Any = (),
    activation_ids: Any = (),
    result: Any = None,
    error: Any = None,
    caused_by: Any = None,
    resource_leases: Any = (),
    created_at: str | None = None,
    **fields: Any,
) -> dict[str, Any]:
    """Build the portable durable state for a single Process run."""
    if not process_type:
        raise ValueError("process_type is required")
    if state not in PROCESS_STATES:
        raise InvalidProcessState(state)
    timestamp = created_at or _now()
    pending = [deepcopy(item) for item in (pending_activations or ())]
    record = {
        "process_id": process_id or new_process_id(),
        "run_id": run_id or new_run_id(),
        "process_type": str(process_type),
        "definition_version": str(definition_version),
        "state": state,
        "pending_activations": pending,
        "activation_ids": [str(item) for item in (activation_ids or ())],
        "result": deepcopy(result),
        "error": deepcopy(error),
        "caused_by": deepcopy(caused_by),
        "resource_leases": [deepcopy(item) for item in (resource_leases or ())],
        "created_at": timestamp,
        "updated_at": fields.pop("updated_at", timestamp),
    }
    # mailbox remains an alias for hosts which have not moved to activation queues.
    mailbox = fields.pop("mailbox", None)
    record["mailbox"] = pending if mailbox is None else list(deepcopy(mailbox))
    record.update(deepcopy(fields))
    return record


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
    updated["updated_at"] = _now()
    if reason is not None:
        updated["wait_reason"] = reason
    elif target in {READY, RUNNING, TERMINATED}:
        updated.pop("wait_reason", None)
    return dict(updated)
