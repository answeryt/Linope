"""Reject a wait that would circle back or keep holding another process."""

from __future__ import annotations

import threading
from contextlib import contextmanager

_local = threading.local()


def _held() -> set[str]:
    held = getattr(_local, "held", None)
    if held is None:
        held = set()
        _local.held = held
    return held


def _stack() -> list[str]:
    stack = getattr(_local, "stack", None)
    if stack is None:
        stack = []
        _local.stack = stack
    return stack


@contextmanager
def holding_exclusive(process_id: str):
    """Remember that this thread still occupies one exclusive process."""
    held = _held()
    held.add(process_id)
    try:
        yield
    finally:
        held.discard(process_id)


def check_wait(target_process_id: str, caller_id: str | None) -> None:
    """Refuse a wait that still holds another process, or that loops back."""
    others = _held() - {target_process_id}
    if others:
        raise RuntimeError("手里占着独占进程时不能等待另一张回执")
    stack = _stack()
    if caller_id is not None and (caller_id == target_process_id or target_process_id in stack):
        raise RuntimeError("同步委托会绕回自己")
    if caller_id is not None and caller_id in stack and caller_id == target_process_id:
        raise RuntimeError("同步委托会绕回自己")


@contextmanager
def delegating(caller_id: str | None, target_process_id: str):
    check_wait(target_process_id, caller_id)
    stack = _stack()
    if caller_id is not None:
        stack.append(caller_id)
    try:
        yield
    finally:
        if caller_id is not None and stack:
            stack.pop()
