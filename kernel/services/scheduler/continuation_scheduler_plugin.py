# -*- coding: utf-8 -*-
"""Scheduler-owned dispatch of persisted Process continuations."""

from __future__ import annotations

import inspect
import time
from collections.abc import Callable, Mapping
from copy import deepcopy
from typing import Any


PLUGIN_NAME = "kernel_continuation_scheduler"
PLUGIN_VERSION = "1.0"


async def _call(function: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    result = function(*args, **kwargs)
    return await result if inspect.isawaitable(result) else result


def _default_evaluate(expr: Any, world: Mapping[str, Any]) -> Any:
    cached = getattr(_default_evaluate, "_evaluate", None)
    if cached is None:
        import importlib.util
        from pathlib import Path

        path = (
            Path(__file__).resolve().parents[2]
            / "process"
            / "continuation"
            / "expression_plugin.py"
        )
        spec = importlib.util.spec_from_file_location(
            "kernel_process_expression_eval", path
        )
        if spec is None or spec.loader is None:
            raise RuntimeError("cannot load continuation expression plugin")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        cached = module.evaluate
        _default_evaluate._evaluate = cached
    return cached(expr, world)


class ContinuationScheduler:
    """Decide when continuation expressions may become Process Activations."""

    def __init__(
        self,
        *,
        continuations: Any,
        processes: Any,
        dispatch: Callable[[Mapping[str, Any]], Any],
        policy: Callable[[Mapping[str, Any], Mapping[str, Any]], Any] | None = None,
        evaluator: Callable[..., Any] | None = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        if continuations is None or processes is None or not callable(dispatch):
            raise TypeError("continuations, processes, and dispatch are required")
        self.continuations = continuations
        self.processes = processes
        self.dispatch = dispatch
        self.policy = policy
        self.evaluator = evaluator or _default_evaluate
        self.clock = clock

    async def submit(self, record: Mapping[str, Any]) -> dict[str, Any]:
        """Persist an intent and dispatch it only when the expression permits."""
        stored = dict(self.continuations.create(record))
        await self.dispatch_ready()
        return dict(
            self.continuations.require(str(stored["continuation_id"]))
        )

    async def dispatch_ready(
        self, event: Mapping[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Dispatch pending continuations whose expressions are currently true."""
        dispatched: list[dict[str, Any]] = []
        for record in self.continuations.list(status="pending"):
            result = self.evaluator(record.get("when"), self._world(record, event))
            latches = getattr(result, "latches", None)
            if latches:
                observer = getattr(self.continuations, "observe", None)
                if callable(observer):
                    observer(str(record["continuation_id"]), latches=latches)
                    record = self.continuations.require(
                        str(record["continuation_id"])
                    )
            if not bool(getattr(result, "value", result)):
                continue
            process = self.processes.get(str(record["process_id"]))
            if process is None:
                self.continuations.cancel(str(record["continuation_id"]))
                continue
            if str(process.get("run_id")) != str(record.get("run_id")):
                self.continuations.cancel(str(record["continuation_id"]))
                continue
            if str(process.get("state")) == "terminated":
                self.continuations.cancel(str(record["continuation_id"]))
                continue
            if str(process.get("state")) == "suspended":
                continue
            if self.policy is not None and not bool(
                await _call(self.policy, deepcopy(record), deepcopy(process))
            ):
                continue
            continuation_id = str(record["continuation_id"])
            claimed = self.continuations.claim(continuation_id)
            if claimed is None:
                continue
            activation_id = f"continuation:{record['continuation_id']}"
            activation = {
                "activation_id": activation_id,
                "process_id": str(record["process_id"]),
                "process_type": str(process["process_type"]),
                "definition_version": str(
                    process.get("definition_version") or "1"
                ),
                "input": deepcopy(record.get("input")),
                "reason": str(record.get("reason") or "continuation"),
                "priority": int(record.get("priority") or 0),
                "caused_by": {
                    "type": "continuation",
                    "continuation_id": str(record["continuation_id"]),
                    "execution_id": str(record["source_execution_id"]),
                },
            }
            try:
                await _call(self.dispatch, activation)
            except BaseException:
                self.continuations.release(continuation_id)
                raise
            dispatched.append(
                self.continuations.mark_dispatched(
                    continuation_id,
                    activation_id=activation_id,
                )
            )
        return dispatched

    async def notify(self, event: Mapping[str, Any]) -> list[dict[str, Any]]:
        """Record one fact on pending continuations, then re-evaluate them."""
        payload = deepcopy(dict(event))
        observer = getattr(self.continuations, "observe", None)
        if callable(observer):
            for record in self.continuations.list(status="pending"):
                observer(str(record["continuation_id"]), event=payload)
        return await self.dispatch_ready(payload)

    async def trigger(self, event: Mapping[str, Any]) -> list[dict[str, Any]]:
        """Compatibility-friendly name for event-triggered dispatch."""
        return await self.notify(event)

    def _world(
        self,
        record: Mapping[str, Any],
        event: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        facts = record.get("facts") or {}
        created = record.get("created_at_ts")
        if created is None:
            created = self.clock()
        return {
            "now": float(self.clock()),
            "created_at": float(created),
            "event": None if event is None else deepcopy(dict(event)),
            "events": [
                deepcopy(dict(item))
                for item in (facts.get("events") or ())
                if isinstance(item, Mapping)
            ],
            "latches": deepcopy(dict(facts.get("latches") or {})),
            "process_id": record.get("process_id"),
            "run_id": record.get("run_id"),
        }
