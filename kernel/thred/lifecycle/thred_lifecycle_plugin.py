# -*- coding: utf-8 -*-
"""Attach, run, wait, suspend, and complete Agent Threads.

table is required. transition / build_thread / new_thread_id are injected
so this file never imports context, state, or table siblings.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any
from uuid import uuid4


PLUGIN_NAME = "kernel_thred_lifecycle"
PLUGIN_VERSION = "1.0"

BuildThread = Callable[..., Mapping[str, Any]]
Transition = Callable[..., Mapping[str, Any]]
NewId = Callable[[], str]


def _new_id() -> str:
    return uuid4().hex


def _default_thread(name: str, **fields: Any) -> dict[str, Any]:
    record = {
        "thread_id": fields.pop("thread_id", None) or _new_id(),
        "name": name,
        "process_id": fields.pop("process_id", None),
        "state": fields.pop("state", "ready"),
        "wait_reason": fields.pop("wait_reason", None),
        "parent_id": fields.pop("parent_id", None),
        "children": list(fields.pop("children", None) or ()),
        "execution_id": fields.pop("execution_id", None),
    }
    record.update(fields)
    return record


def _put(table: Any, record: Mapping[str, Any]) -> dict[str, Any]:
    stored = table.put(record)
    return dict(stored) if isinstance(stored, Mapping) else dict(record)


def _require(table: Any, thread_id: str) -> dict[str, Any]:
    require = getattr(table, "require", None)
    if callable(require):
        return dict(require(thread_id))
    getter = getattr(table, "get", None)
    if not callable(getter):
        raise TypeError("table must provide get or require")
    record = getter(thread_id)
    if record is None:
        raise KeyError(thread_id)
    return dict(record)


class ThreadLifecycle:
    """Lifecycle operations over an injected thread table."""

    def __init__(
        self,
        table: Any,
        *,
        transition: Transition | None = None,
        build_thread: BuildThread | None = None,
        new_thread_id: NewId | None = None,
    ) -> None:
        if table is None:
            raise TypeError("table is required")
        self.table = table
        self.transition = transition
        self.build_thread = build_thread or _default_thread
        self.new_thread_id = new_thread_id or _new_id

    def attach(self, name: str, **fields: Any) -> dict[str, Any]:
        fields.setdefault("thread_id", self.new_thread_id())
        record = dict(self.build_thread(name, **fields))
        stored = _put(self.table, record)
        parent_id = stored.get("parent_id")
        if parent_id:
            self._append_child(str(parent_id), str(stored.get("thread_id")))
        return stored

    def run(self, thread_id: str) -> dict[str, Any]:
        return self._move(thread_id, "running")

    def ready(self, thread_id: str) -> dict[str, Any]:
        return self._move(thread_id, "ready")

    def wait(self, thread_id: str, *, reason: str | None = None) -> dict[str, Any]:
        return self._move(thread_id, "waiting", reason=reason)

    def suspend(self, thread_id: str, *, reason: str | None = None) -> dict[str, Any]:
        return self._move(thread_id, "suspended", reason=reason)

    def complete(self, thread_id: str) -> dict[str, Any]:
        return self._move(thread_id, "done")

    def fail(self, thread_id: str, *, reason: str | None = None) -> dict[str, Any]:
        return self._move(thread_id, "failed", reason=reason)

    def cancel(self, thread_id: str) -> dict[str, Any]:
        return self._move(thread_id, "cancelled")

    def spawn(self, parent_id: str, *, name: str, **fields: Any) -> dict[str, Any]:
        parent = _require(self.table, parent_id)
        fields.setdefault("parent_id", parent_id)
        fields.setdefault("process_id", parent.get("process_id"))
        return self.attach(name, **fields)

    def _append_child(self, parent_id: str, child_id: str) -> None:
        try:
            parent = _require(self.table, parent_id)
        except KeyError:
            return
        children = list(parent.get("children") or ())
        if child_id not in children:
            children.append(child_id)
        parent = dict(parent)
        parent["children"] = children
        _put(self.table, parent)

    def _move(
        self,
        thread_id: str,
        target: str,
        *,
        reason: str | None = None,
    ) -> dict[str, Any]:
        record = _require(self.table, thread_id)
        if self.transition is not None:
            record = dict(self.transition(record, target, reason=reason))
        else:
            record = dict(record)
            record["state"] = target
            if reason is not None:
                record["wait_reason"] = reason
        return _put(self.table, record)
