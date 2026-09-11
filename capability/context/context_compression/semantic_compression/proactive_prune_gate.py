"""Prompt-cache-aware commit/reclaim gate for proactive pruning."""

from __future__ import annotations

from typing import Any, Callable


def commit_proactive_prune(
    messages: list[dict[str, Any]],
    *,
    current_tokens: int,
    trigger_tokens: int,
    min_reclaim_tokens: int,
    build_candidate: Callable[[list[dict[str, Any]]], list[dict[str, Any]]],
    estimate_messages: Callable[[list[dict[str, Any]]], int],
    eligibility_callback: Callable[[list[dict[str, Any]]], bool] | None = None,
) -> list[dict[str, Any]]:
    """Return the original object unless a candidate clears every gate."""
    if trigger_tokens <= 0 or current_tokens < trigger_tokens:
        return messages
    if eligibility_callback and not eligibility_callback(messages):
        return messages
    candidate = build_candidate(messages)
    if candidate is messages or candidate == messages:
        return messages
    reclaimed = estimate_messages(messages) - estimate_messages(candidate)
    if reclaimed < max(0, min_reclaim_tokens):
        return messages
    return candidate
