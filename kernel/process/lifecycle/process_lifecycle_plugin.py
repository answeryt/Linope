# -*- coding: utf-8 -*-
"""Create, start, stop, kill, and spawn Agent Processes.

table is required. transition / build_pcb / new_process_id are injected
so this file never imports PCB, state, or table siblings.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any
from uuid import uuid4


PLUGIN_NAME = "kernel_process_lifecycle"
PLUGIN_VERSION = "1.0"

BuildPcb = Callable[..., Mapping[str, Any]]
Transition = Callable[..., Mapping[str, Any]]
NewId = Callable[[], str]


def _new_id() -> str:
    return uuid4().hex


def _default_pcb(agent: str, **fields: Any) -> dict[str, Any]:
    record = {
        "process_id": fields.pop("process_id", None) or _new_id(),
        "agent": agent,
        "state": fields.pop("state", "new"),
        "memory": dict(fields.pop("memory", None) or {}),
        "context": dict(fields.pop("context", None) or {}),
        "parent_id": fields.pop("parent_id", None),
        "children": list(fields.pop("children", None) or ()),
        "threads": list(fields.pop("threads", None) or ()),
        "budget": dict(fields.pop("budget", None) or {}),
    }
    record.update(fields)
    return record


def _put(table: Any, record: Mapping[str, Any]) -> dict[str, Any]:
    stored = table.put(record)
    return dict(stored) if isinstance(stored, Mapping) else dict(record)


def _require(table: Any, process_id: str) -> dict[str, Any]:
    require = getattr(table, "require", None)
    if callable(require):
        return dict(require(process_id))
    getter = getattr(table, "get", None)
    if not callable(getter):
        raise TypeError("table must provide get or require")
    record = getter(process_id)
    if record is None:
        raise KeyError(process_id)
    return dict(record)


class ProcessLifecycle:
    """Lifecycle operations over an injected process table."""

    def __init__(
        self,
        table: Any,
        *,
        transition: Transition | None = None,
        build_pcb: BuildPcb | None = None,
        new_process_id: NewId | None = None,
    ) -> None:
        if table is None:
            raise TypeError("table is required")
        self.table = table
        self.transition = transition
        self.build_pcb = build_pcb or _default_pcb
        self.new_process_id = new_process_id or _new_id

    def create(self, agent: str, **fields: Any) -> dict[str, Any]:
        fields.setdefault("process_id", self.new_process_id())
        record = dict(self.build_pcb(agent, **fields))
        return _put(self.table, record)

    def start(self, process_id: str) -> dict[str, Any]:
        return self._move(process_id, "running")

    def ready(self, process_id: str) -> dict[str, Any]:
        return self._move(process_id, "ready")

    def wait(self, process_id: str, *, reason: str | None = None) -> dict[str, Any]:
        return self._move(process_id, "waiting", reason=reason)

    def suspend(self, process_id: str, *, reason: str | None = None) -> dict[str, Any]:
        return self._move(process_id, "suspended", reason=reason)

    def stop(self, process_id: str) -> dict[str, Any]:
        return self._move(process_id, "terminated")

    def kill(self, process_id: str) -> dict[str, Any]:
        return self._move(process_id, "terminated", reason="killed")

    def spawn(self, parent_id: str, *, agent: str, **fields: Any) -> dict[str, Any]:
        parent = _require(self.table, parent_id)
        fields.setdefault("parent_id", parent_id)
        child = self.create(agent, **fields)
        children = list(parent.get("children") or ())
        child_id = str(child.get("process_id"))
        if child_id not in children:
            children.append(child_id)
        parent = dict(parent)
        parent["children"] = children
        _put(self.table, parent)
        return child

    def _move(
        self,
        process_id: str,
        target: str,
        *,
        reason: str | None = None,
    ) -> dict[str, Any]:
        record = _require(self.table, process_id)
        if self.transition is not None:
            record = dict(self.transition(record, target, reason=reason))
        else:
            record = dict(record)
            record["state"] = target
            if reason is not None:
                record["wait_reason"] = reason
        return _put(self.table, record)
