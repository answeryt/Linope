"""JSON-valid recursive truncation of tool-call arguments."""

from __future__ import annotations

import json
from typing import Any, Callable


def truncate_tool_call_arguments(
    messages: list[dict[str, Any]],
    *,
    should_truncate: Callable[[int, dict[str, Any]], bool] | None = None,
    trigger_chars: int = 500,
    leaf_chars: int = 200,
    suffix: str = "...[truncated]",
) -> list[dict[str, Any]]:
    """Truncate long string leaves without ever slicing raw JSON."""

    def shrink(value: Any) -> Any:
        if isinstance(value, str):
            return value[:leaf_chars] + suffix if len(value) > leaf_chars else value
        if isinstance(value, dict):
            return {key: shrink(item) for key, item in value.items()}
        if isinstance(value, list):
            return [shrink(item) for item in value]
        return value

    result = list(messages)
    changed = False
    for index, message in enumerate(messages):
        if message.get("role") != "assistant" or (should_truncate and not should_truncate(index, message)):
            continue
        calls = message.get("tool_calls")
        if not isinstance(calls, list):
            continue
        new_calls: list[Any] = []
        message_changed = False
        for call in calls:
            if not isinstance(call, dict):
                new_calls.append(call)
                continue
            function = call.get("function")
            arguments = function.get("arguments") if isinstance(function, dict) else None
            if not isinstance(arguments, str) or len(arguments) <= trigger_chars:
                new_calls.append(call)
                continue
            try:
                parsed = json.loads(arguments)
            except (TypeError, ValueError):
                new_calls.append(call)
                continue
            replacement = json.dumps(shrink(parsed), ensure_ascii=False)
            if replacement != arguments:
                call = {**call, "function": {**function, "arguments": replacement}}
                message_changed = True
            new_calls.append(call)
        if message_changed:
            result[index] = {**message, "tool_calls": new_calls}
            changed = True
    return result if changed else messages
