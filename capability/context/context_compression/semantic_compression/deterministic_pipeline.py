"""Callback-only orchestration for deterministic multi-pass compression."""

from __future__ import annotations

from typing import Any, Callable, Iterable


MessageTransform = Callable[[list[dict[str, Any]]], list[dict[str, Any]]]


def run_deterministic_pipeline(
    messages: list[dict[str, Any]],
    *,
    passes: Iterable[MessageTransform],
) -> list[dict[str, Any]]:
    """Run Host-composed passes in order without importing any plugin."""
    current = messages
    for transform in passes:
        candidate = transform(current)
        if not isinstance(candidate, list) or any(not isinstance(item, dict) for item in candidate):
            raise TypeError("compression pass must return list[dict]")
        current = candidate
    return current
