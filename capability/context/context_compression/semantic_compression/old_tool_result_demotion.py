"""Demote old tool results using Host-provided policy and summaries."""

from __future__ import annotations

from typing import Any, Callable


def demote_old_tool_results(
    messages: list[dict[str, Any]],
    *,
    should_demote: Callable[[int, dict[str, Any]], bool],
    summary_callback: Callable[[str, str, str], str],
    image_part_callback: Callable[[list[Any]], list[Any] | None] | None = None,
    protect_callback: Callable[[int, str, str, dict[str, Any]], bool] | None = None,
) -> list[dict[str, Any]]:
    """Demote selected results; helpers and protection decisions are injected."""
    calls: dict[str, tuple[str, str]] = {}
    for message in messages:
        for call in message.get("tool_calls") or []:
            if not isinstance(call, dict):
                continue
            function = call.get("function") if isinstance(call.get("function"), dict) else {}
            call_id = str(call.get("call_id") or call.get("id") or "")
            if call_id:
                calls[call_id] = (
                    str(function.get("name") or "unknown"),
                    str(function.get("arguments") or ""),
                )

    result = list(messages)
    changed = False
    for index, message in enumerate(messages):
        if message.get("role") != "tool" or not should_demote(index, message):
            continue
        content = message.get("content")
        if isinstance(content, list) and image_part_callback:
            replacement = image_part_callback(content)
            if replacement is not None and replacement != content:
                result[index] = {**message, "content": replacement}
                changed = True
            continue
        if isinstance(content, dict) and content.get("_multimodal"):
            text = str(content.get("text_summary") or "[screenshot removed to save context]")
            result[index] = {**message, "content": f"[screenshot removed] {text[:200]}"}
            changed = True
            continue
        if not isinstance(content, str) or not content:
            continue
        name, arguments = calls.get(str(message.get("tool_call_id") or ""), ("unknown", ""))
        if protect_callback and protect_callback(index, name, arguments, message):
            continue
        replacement = summary_callback(name, arguments, content)
        if replacement != content:
            result[index] = {**message, "content": replacement}
            changed = True
    return result if changed else messages
