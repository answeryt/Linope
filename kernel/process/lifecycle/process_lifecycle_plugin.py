# -*- coding: utf-8 -*-
"""Durable Process lifecycle over an injected store."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


PLUGIN_NAME = "kernel_process_lifecycle"
PLUGIN_VERSION = "1.0"

BuildRun = Callable[..., Mapping[str, Any]]
Transition = Callable[..., Mapping[str, Any]]
NewId = Callable[[], str]


def _new_id() -> str:
    return uuid4().hex


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_run(process_type: str, **fields: Any) -> dict[str, Any]:
    timestamp = _now()
    pending = list(deepcopy(fields.pop("pending_activations", ())))
    record = {
        "process_id": fields.pop("process_id", None) or _new_id(),
        "run_id": fields.pop("run_id", None) or _new_id(),
        "process_type": process_type,
        "definition_version": str(fields.pop("definition_version", "1")),
        "state": fields.pop("state", "new"),
        "pending_activations": pending,
        "mailbox": list(deepcopy(fields.pop("mailbox", pending))),
        "activation_ids": list(fields.pop("activation_ids", None) or ()),
        "resource_leases": list(fields.pop("resource_leases", None) or ()),
        "wait_condition": fields.pop("wait_condition", None),
        "caused_by": fields.pop("caused_by", None),
        "result": fields.pop("result", None),
        "error": fields.pop("error", None),
        "created_at": fields.pop("created_at", timestamp),
        "updated_at": fields.pop("updated_at", timestamp),
    }
    record.update(fields)
    return record


def _put(store: Any, record: Mapping[str, Any]) -> dict[str, Any]:
    putter = getattr(store, "put", None)
    if not callable(putter):
        raise TypeError("store must provide put")
    stored = putter(deepcopy(dict(record)))
    return dict(stored) if isinstance(stored, Mapping) else dict(record)


def _require(store: Any, process_id: str) -> dict[str, Any]:
    require = getattr(store, "require", None)
    if callable(require):
        return dict(require(process_id))
    getter = getattr(store, "get", None)
    if not callable(getter):
        raise TypeError("store must provide get or require")
    record = getter(process_id)
    if record is None:
        raise KeyError(process_id)
    return dict(record)


class ProcessLifecycle:
    """State changes and activation de-duplication over an injected store."""

    def __init__(
        self,
        store: Any = None,
        *,
        transition: Transition | None = None,
        build_process_run: BuildRun | None = None,
        build_pcb: BuildRun | None = None,
        new_process_id: NewId | None = None,
        new_run_id: NewId | None = None,
        table: Any = None,
    ) -> None:
        selected_store = store if store is not None else table
        if selected_store is None:
            raise TypeError("store is required")
        self.store = selected_store
        self.table = selected_store
        self.transition = transition
        self.build_process_run = build_process_run or build_pcb or _default_run
        self.build_pcb = self.build_process_run
        self.new_process_id = new_process_id or _new_id
        self.new_run_id = new_run_id or _new_id

    def create(self, process_type: str, **fields: Any) -> dict[str, Any]:
        fields.setdefault("process_id", self.new_process_id())
        fields.setdefault("run_id", self.new_run_id())
        record = dict(self.build_process_run(process_type, **fields))
        creator = getattr(self.store, "create", None)
        if callable(creator):
            return dict(creator(record))
        return _put(self.store, record)

    def activate(
        self,
        process_id: str,
        activation: Mapping[str, Any],
    ) -> dict[str, Any]:
        updater = getattr(self.store, "update", None)
        if callable(updater):
            activation_copy = deepcopy(dict(activation))

            def apply(record: dict[str, Any]) -> dict[str, Any]:
                if record.get("state") == "terminated":
                    raise RuntimeError("terminated process cannot be activated")
                activation_id = activation_copy.get("activation_id")
                activation_ids = [
                    str(item) for item in (record.get("activation_ids") or ())
                ]
                if (
                    activation_id is not None
                    and str(activation_id) in activation_ids
                ):
                    return record
                pending = [
                    deepcopy(dict(item))
                    for item in (
                        record.get("pending_activations")
                        or record.get("mailbox")
                        or ()
                    )
                ]
                pending.append(deepcopy(activation_copy))
                record["pending_activations"] = pending
                record["mailbox"] = deepcopy(pending)
                if activation_id is not None:
                    activation_ids.append(str(activation_id))
                    record["activation_ids"] = activation_ids[-1024:]
                record["wait_condition"] = None
                if record.get("state") in {"new", "waiting", "suspended"}:
                    if self.transition is not None:
                        record = dict(self.transition(record, "ready"))
                    else:
                        record["state"] = "ready"
                record["updated_at"] = _now()
                return record

            return dict(updater(process_id, apply))

        record = _require(self.store, process_id)
        if record.get("state") == "terminated":
            raise RuntimeError("terminated process cannot be activated")
        activation_id = activation.get("activation_id")
        activation_ids = [str(item) for item in (record.get("activation_ids") or ())]
        if activation_id is not None and str(activation_id) in activation_ids:
            return record
        pending_source = (
            record.get("mailbox")
            if "mailbox" in record
            else record.get("pending_activations")
        )
        pending = [
            deepcopy(dict(item))
            for item in (pending_source or ())
        ]
        pending.append(deepcopy(dict(activation)))
        record["pending_activations"] = pending
        record["mailbox"] = deepcopy(pending)
        if activation_id is not None:
            activation_ids.append(str(activation_id))
            record["activation_ids"] = activation_ids[-1024:]
        record["wait_condition"] = None
        record["updated_at"] = _now()
        stored = _put(self.store, record)
        if stored.get("state") in {"new", "waiting", "suspended"}:
            return self._move(process_id, "ready")
        return stored

    def run(self, process_id: str) -> dict[str, Any]:
        return self._move(process_id, "running")

    def wait(
        self,
        process_id: str,
        *,
        condition: Mapping[str, Any] | None = None,
        reason: str | None = None,
    ) -> dict[str, Any]:
        record = _require(self.store, process_id)
        record["wait_condition"] = None if condition is None else dict(condition)
        _put(self.store, record)
        return self._move(process_id, "waiting", reason=reason)

    def resume(self, process_id: str) -> dict[str, Any]:
        record = _require(self.store, process_id)
        record["wait_condition"] = None
        _put(self.store, record)
        return self._move(process_id, "ready")

    def complete(self, process_id: str, *, result: Any = None) -> dict[str, Any]:
        record = _require(self.store, process_id)
        record["result"] = deepcopy(result)
        record["error"] = None
        record["outcome"] = "completed"
        _put(self.store, record)
        return self._move(process_id, "terminated")

    def fail(
        self,
        process_id: str,
        *,
        reason: str | None = None,
        error: Any = None,
    ) -> dict[str, Any]:
        record = _require(self.store, process_id)
        record["error"] = deepcopy(
            error if error is not None else {"message": str(reason or "process failed")}
        )
        record["outcome"] = "failed"
        _put(self.store, record)
        return self._move(process_id, "terminated", reason=reason)

    def cancel(self, process_id: str) -> dict[str, Any]:
        record = _require(self.store, process_id)
        record["outcome"] = "cancelled"
        record["error"] = {"message": "cancelled", "type": "ProcessCancelled"}
        _put(self.store, record)
        return self._move(process_id, "terminated", reason="cancelled")

    def _move(
        self,
        process_id: str,
        target: str,
        *,
        reason: str | None = None,
    ) -> dict[str, Any]:
        record = _require(self.store, process_id)
        if self.transition is not None:
            record = dict(self.transition(record, target, reason=reason))
        else:
            record = dict(record)
            record["state"] = target
            if reason is not None:
                record["wait_reason"] = reason
        record["updated_at"] = _now()
        return _put(self.store, record)
