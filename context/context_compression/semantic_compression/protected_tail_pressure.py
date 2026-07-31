"""Pressure demotion inside an otherwise protected tail."""

from __future__ import annotations

from typing import Any, Callable


def demote_protected_tail_under_pressure(
    messages: list[dict[str, Any]],
    *,
    protected_start: int,
    soft_token_limit: int,
    estimate_messages: Callable[[list[dict[str, Any]]], int],
    summary_callback: Callable[[str, str, str], str],
    keep_recent: int = 3,
    truncate_args_callback: Callable[[list[dict[str, Any]]], list[dict[str, Any]]] | None = None,
) -> list[dict[str, Any]]:
    """Demote oldest protected results until the injected estimate fits."""
    if not messages or soft_token_limit <= 0:
        return messages
    start = max(0, min(protected_start, len(messages)))
    if estimate_messages(messages[start:]) <= soft_token_limit:
        return messages

    calls: dict[str, tuple[str, str]] = {}
    for message in messages:
        for call in message.get("tool_calls") or []:
            if isinstance(call, dict):
                function = call.get("function") if isinstance(call.get("function"), dict) else {}
                call_id = str(call.get("call_id") or call.get("id") or "")
                if call_id:
                    calls[call_id] = (
                        str(function.get("name") or "unknown"),
                        str(function.get("arguments") or ""),
                    )

    result = list(messages)
    changed = False
    ordinary_end = max(start, len(result) - max(0, keep_recent))
    candidates = list(range(start, ordinary_end))
    candidates.extend(
        index for index in range(ordinary_end, len(result))
        if result[index].get("role") == "tool"
    )
    for index in candidates:
        if estimate_messages(result[start:]) <= soft_token_limit:
            break
        message = result[index]
        content = message.get("content")
        if message.get("role") != "tool" or not isinstance(content, str) or not content:
            continue
        name, arguments = calls.get(str(message.get("tool_call_id") or ""), ("unknown", ""))
        replacement = summary_callback(name, arguments, content)
        if replacement != content:
            result[index] = {**message, "content": replacement}
            changed = True

    if truncate_args_callback and estimate_messages(result[start:]) > soft_token_limit:
        truncated = truncate_args_callback(result)
        if truncated is not result:
            result = truncated
            changed = True
    return result if changed else messages
