# -*- coding: utf-8 -*-
"""Composable Continuation expressions: primitives plus spatiotemporal operators."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from copy import deepcopy
from typing import Any


PLUGIN_NAME = "kernel_process_expression"
PLUGIN_VERSION = "1.0"

LANGUAGE_VERSION = "1"
COMBINATORS = frozenset({"all", "any", "not", "once", "within", "then"})
EVENT_TYPE_ALIASES = {
    "task": frozenset({"task", "task.completed"}),
    "process": frozenset({"process", "process.completed"}),
}


class UnknownPrimitive(KeyError):
    """Raised when an expression names a primitive the Host has not injected."""


class Evaluation:
    """Result of one expression check, including latch progress for later ticks."""

    def __init__(
        self,
        value: bool,
        *,
        next_check_at: float | None = None,
        latches: Mapping[str, Any] | None = None,
        matched_index: int | None = None,
    ) -> None:
        self.value = bool(value)
        self.next_check_at = next_check_at
        self.latches = {} if latches is None else dict(latches)
        self.matched_index = matched_index


PrimitiveFn = Callable[[Mapping[str, Any], Mapping[str, Any]], Evaluation]


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))


def _as_tree(value: Any) -> dict[str, Any]:
    # Plugins are loaded by file path, so Expression class identity is not stable.
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict) and not isinstance(value, Mapping):
        return deepcopy(dict(to_dict()))
    tree = getattr(value, "tree", None)
    if isinstance(tree, Mapping):
        return deepcopy(dict(tree))
    if isinstance(value, Mapping):
        return deepcopy(dict(value))
    raise TypeError("expression must be an Expression or mapping")


def _normalize_node(node: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(node, Mapping) or "op" not in node:
        raise ValueError("expression node requires op")
    op = str(node["op"])
    if op == "primitive":
        name = str(node.get("name") or "")
        if not name:
            raise ValueError("primitive requires name")
        params = dict(node.get("params") or {})
        return {
            "op": "primitive",
            "name": name,
            "version": str(node.get("version") or "1"),
            "params": params,
        }
    if op in {"all", "any", "then"}:
        args = [_normalize_node(_as_tree(item)) for item in (node.get("args") or ())]
        if not args:
            raise ValueError(f"{op} requires at least one argument")
        flat: list[dict[str, Any]] = []
        for item in args:
            if item.get("op") == op and op != "then":
                flat.extend(item["args"])
            else:
                flat.append(item)
        if op != "then":
            unique: list[dict[str, Any]] = []
            seen: set[str] = set()
            for item in sorted(flat, key=_canonical):
                key = _canonical(item)
                if key not in seen:
                    seen.add(key)
                    unique.append(item)
            flat = unique
        return {"op": op, "args": flat}
    if op == "not":
        return {"op": "not", "arg": _normalize_node(_as_tree(node["arg"]))}
    if op == "once":
        return {"op": "once", "arg": _normalize_node(_as_tree(node["arg"]))}
    if op == "within":
        seconds = float(node.get("seconds") or 0)
        if seconds < 0:
            raise ValueError("within seconds cannot be negative")
        return {
            "op": "within",
            "seconds": seconds,
            "arg": _normalize_node(_as_tree(node["arg"])),
        }
    raise ValueError(f"unknown expression op: {op}")


def normalize_expression(value: Any | None = None) -> dict[str, Any]:
    """Return a versioned, flattened, deterministically ordered expression tree."""
    if value is None:
        raw = {
            "op": "primitive",
            "name": "time.always",
            "version": "1",
            "params": {},
        }
    else:
        raw = _as_tree(value)
        raw.pop("language", None)
    return {"language": LANGUAGE_VERSION, **_normalize_node(raw)}


class Expression:
    """Immutable portable expression. Combine with ``&``, ``|``, and ``~``."""

    def __init__(self, tree: Mapping[str, Any]) -> None:
        self.tree = normalize_expression(tree)

    def __and__(self, other: Any) -> "Expression":
        return Expression({"op": "all", "args": [self.tree, _as_tree(other)]})

    def __or__(self, other: Any) -> "Expression":
        return Expression({"op": "any", "args": [self.tree, _as_tree(other)]})

    def __invert__(self) -> "Expression":
        return Expression({"op": "not", "arg": self.tree})

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Expression) and self.tree == other.tree

    def __hash__(self) -> int:
        return hash(_canonical(self.tree))

    def __bool__(self) -> bool:
        raise TypeError("compose expressions with &, |, and ~; and/or/not are not portable")

    def to_dict(self) -> dict[str, Any]:
        return deepcopy(self.tree)


def always() -> Expression:
    return Expression(
        {"op": "primitive", "name": "time.always", "version": "1", "params": {}}
    )


def after(seconds: float) -> Expression:
    value = float(seconds)
    if value < 0:
        raise ValueError("after seconds cannot be negative")
    return Expression(
        {
            "op": "primitive",
            "name": "time.after",
            "version": "1",
            "params": {"seconds": value},
        }
    )


def at(due_at: float) -> Expression:
    return Expression(
        {
            "op": "primitive",
            "name": "time.at",
            "version": "1",
            "params": {"due_at": float(due_at)},
        }
    )


def event(event_type: str, **filters: Any) -> Expression:
    if not event_type:
        raise ValueError("event_type is required")
    return Expression(
        {
            "op": "primitive",
            "name": "event.observed",
            "version": "1",
            "params": {"event_type": str(event_type), **deepcopy(filters)},
        }
    )


def task(task_id: str, *, state: str | None = None, **filters: Any) -> Expression:
    params = {"task_id": str(task_id), **deepcopy(filters)}
    if state is not None:
        params["state"] = str(state)
    return event("task", **params)


def process(process_id: str, *, state: str | None = None, **filters: Any) -> Expression:
    params = {"process_id": str(process_id), **deepcopy(filters)}
    if state is not None:
        params["state"] = str(state)
    return event("process", **params)


def once(expr: Any) -> Expression:
    """Latch the first time ``expr`` is true so later ticks cannot un-satisfy it."""
    return Expression({"op": "once", "arg": _as_tree(expr)})


def within(seconds: float, expr: Any) -> Expression:
    """Require ``expr`` to become true before ``seconds`` elapse."""
    return Expression({"op": "within", "seconds": float(seconds), "arg": _as_tree(expr)})


def then(*exprs: Any) -> Expression:
    """Satisfy arguments in order, using event cursors so later facts cannot rewrite earlier ones."""
    if not exprs:
        raise ValueError("then requires at least one argument")
    return Expression({"op": "then", "args": [_as_tree(item) for item in exprs]})


class PrimitiveRegistry:
    """Host-injected evaluators keyed by ``(name, version)``."""

    def __init__(self, initial: Mapping[tuple[str, str], PrimitiveFn] | None = None) -> None:
        self._items: dict[tuple[str, str], PrimitiveFn] = dict(initial or {})

    def register(
        self,
        name: str,
        evaluator: PrimitiveFn,
        *,
        version: str = "1",
    ) -> None:
        if not name or not callable(evaluator):
            raise ValueError("primitive name and evaluator are required")
        self._items[(str(name), str(version))] = evaluator

    def get(self, name: str, version: str = "1") -> PrimitiveFn:
        try:
            return self._items[(str(name), str(version))]
        except KeyError as exc:
            raise UnknownPrimitive(f"{name}@{version}") from exc


def _event_types(event_type: str) -> frozenset[str]:
    return EVENT_TYPE_ALIASES.get(event_type, frozenset({event_type}))


def _event_matches(item: Mapping[str, Any], params: Mapping[str, Any]) -> bool:
    event_type = str(params.get("event_type") or "")
    if item.get("type") not in _event_types(event_type):
        return False
    return all(
        item.get(key) == value
        for key, value in params.items()
        if key != "event_type"
    )


def _evaluate_always(
    _params: Mapping[str, Any], _world: Mapping[str, Any]
) -> Evaluation:
    return Evaluation(True)


def _evaluate_after(params: Mapping[str, Any], world: Mapping[str, Any]) -> Evaluation:
    due = float(world["created_at"]) + float(params.get("seconds") or 0)
    ready = float(world["now"]) >= due
    return Evaluation(ready, next_check_at=None if ready else due)


def _evaluate_at(params: Mapping[str, Any], world: Mapping[str, Any]) -> Evaluation:
    due = float(params["due_at"])
    ready = float(world["now"]) >= due
    return Evaluation(ready, next_check_at=None if ready else due)


def _evaluate_event(params: Mapping[str, Any], world: Mapping[str, Any]) -> Evaluation:
    since = int(world.get("since_event", -1))
    events = [
        item
        for item in (world.get("events") or ())
        if isinstance(item, Mapping)
    ]
    for index, item in enumerate(events):
        if index <= since:
            continue
        if _event_matches(item, params):
            return Evaluation(True, matched_index=index)
    current = world.get("event")
    if isinstance(current, Mapping) and _event_matches(current, params):
        if not events or current is not events[-1]:
            return Evaluation(True, matched_index=len(events))
    return Evaluation(False)


def default_primitives() -> PrimitiveRegistry:
    registry = PrimitiveRegistry()
    registry.register("time.always", _evaluate_always)
    registry.register("time.after", _evaluate_after)
    registry.register("time.at", _evaluate_at)
    registry.register("event.observed", _evaluate_event)
    return registry


DEFAULT_PRIMITIVES = default_primitives()


def _earliest(values: Sequence[float | None]) -> float | None:
    present = [item for item in values if item is not None]
    return min(present) if present else None


def evaluate(
    expr: Any,
    world: Mapping[str, Any],
    *,
    primitives: PrimitiveRegistry | None = None,
    path: str = "",
) -> Evaluation:
    """Evaluate one tree against a world snapshot. Combinators stay Host-independent."""
    tree = normalize_expression(expr)
    registry = primitives or DEFAULT_PRIMITIVES
    return _evaluate_node(tree, world, registry, path or "when")


def _evaluate_node(
    tree: Mapping[str, Any],
    world: Mapping[str, Any],
    primitives: PrimitiveRegistry,
    path: str,
) -> Evaluation:
    op = str(tree["op"])
    if op == "primitive":
        return primitives.get(str(tree["name"]), str(tree.get("version") or "1"))(
            tree.get("params") or {},
            world,
        )
    if op == "all":
        results = [
            _evaluate_node(item, world, primitives, f"{path}/all/{index}")
            for index, item in enumerate(tree["args"])
        ]
        latches: dict[str, Any] = {}
        for item in results:
            latches.update(item.latches)
        return Evaluation(
            all(item.value for item in results),
            next_check_at=_earliest([item.next_check_at for item in results]),
            latches=latches,
        )
    if op == "any":
        results = [
            _evaluate_node(item, world, primitives, f"{path}/any/{index}")
            for index, item in enumerate(tree["args"])
        ]
        latches = {}
        for item in results:
            latches.update(item.latches)
        matched = next((item for item in results if item.value), None)
        return Evaluation(
            matched is not None,
            next_check_at=_earliest([item.next_check_at for item in results]),
            latches=latches,
            matched_index=None if matched is None else matched.matched_index,
        )
    if op == "not":
        inner = _evaluate_node(tree["arg"], world, primitives, f"{path}/not")
        return Evaluation(
            not inner.value,
            next_check_at=inner.next_check_at,
            latches=inner.latches,
        )
    if op == "once":
        latches = dict(world.get("latches") or {})
        if latches.get(path):
            return Evaluation(True, latches={path: True})
        inner = _evaluate_node(tree["arg"], world, primitives, f"{path}/once")
        merged = dict(inner.latches)
        if inner.value:
            merged[path] = True
            return Evaluation(
                True,
                next_check_at=inner.next_check_at,
                latches=merged,
                matched_index=inner.matched_index,
            )
        return Evaluation(False, next_check_at=inner.next_check_at, latches=merged)
    if op == "within":
        deadline = float(world["created_at"]) + float(tree["seconds"])
        inner = _evaluate_node(tree["arg"], world, primitives, f"{path}/within")
        if inner.value and float(world["now"]) <= deadline:
            return Evaluation(
                True,
                latches=inner.latches,
                matched_index=inner.matched_index,
            )
        if float(world["now"]) > deadline:
            return Evaluation(False, latches=inner.latches)
        return Evaluation(
            False,
            next_check_at=_earliest([inner.next_check_at, deadline]),
            latches=inner.latches,
        )
    if op == "then":
        latches = dict(world.get("latches") or {})
        stage = int(latches.get(path) or 0)
        since = int(latches.get(f"{path}/since") or -1)
        merged: dict[str, Any] = {}
        next_check_at = None
        last_match = None
        args = list(tree["args"])
        while stage < len(args):
            child_world = dict(world)
            child_world["since_event"] = since
            inner = _evaluate_node(
                args[stage],
                child_world,
                primitives,
                f"{path}/then/{stage}",
            )
            merged.update(inner.latches)
            next_check_at = _earliest([next_check_at, inner.next_check_at])
            if not inner.value:
                merged[path] = stage
                merged[f"{path}/since"] = since
                return Evaluation(False, next_check_at=next_check_at, latches=merged)
            if inner.matched_index is not None:
                since = inner.matched_index
                last_match = inner.matched_index
            stage += 1
        merged[path] = stage
        merged[f"{path}/since"] = since
        return Evaluation(True, next_check_at=next_check_at, latches=merged, matched_index=last_match)
    raise ValueError(f"unknown expression op: {op}")
