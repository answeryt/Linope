"""Deterministic local fallback when a summary model is unavailable."""

import json
import re
from collections.abc import Callable
from typing import Any


def build_static_fallback(
    messages: list[dict[str, Any]],
    *,
    redactor: Callable[[str], str],
    content_text: Callable[[Any], str],
    is_real_user: Callable[[dict[str, Any]], bool],
    normalize_summary: Callable[[str], str],
    previous_summary: str | None = None,
    reason: str | None = None,
    max_chars: int = 8_000,
    turn_max_chars: int = 700,
) -> str:
    """Extract continuity anchors deterministically and normalize the result."""

    def compact(value: Any) -> str:
        text = re.sub(r"\s+", " ", redactor(content_text(value))).strip()
        if len(text) > turn_max_chars:
            text = text[: max(turn_max_chars - 15, 0)].rstrip() + " ...[truncated]"
        return text

    users: list[str] = []
    actions: list[str] = []
    files: list[str] = []
    blockers: list[str] = []
    recent: list[str] = []
    call_names: dict[str, str] = {}

    for message in messages:
        for call in message.get("tool_calls") or []:
            if not isinstance(call, dict):
                continue
            function = call.get("function") or {}
            name = str(function.get("name") or "?")
            call_id = str(call.get("id") or call.get("call_id") or "")
            if call_id:
                call_names[call_id] = name
            raw = str(function.get("arguments") or "")
            try:
                values = json.loads(raw)
            except (TypeError, ValueError):
                values = raw
            stack = [values]
            while stack:
                item = stack.pop()
                if isinstance(item, dict):
                    for key, value in item.items():
                        if key in {"path", "file_path", "workdir", "output_path"}:
                            candidate = str(value)
                            if candidate not in files:
                                files.append(candidate)
                        stack.append(value)
                elif isinstance(item, list):
                    stack.extend(item)

    for message in messages:
        role = str(message.get("role") or "unknown")
        text = compact(message.get("content"))
        if text:
            recent.append(f"{role.upper()}: {text}")
            recent = recent[-8:]
        if role == "user" and is_real_user(message) and text:
            users.append(text)
        elif role == "assistant":
            names = [
                str((call.get("function") or {}).get("name") or "?")
                for call in message.get("tool_calls") or []
                if isinstance(call, dict)
            ]
            if names:
                actions.append("Called tool(s): " + ", ".join(names[:6]))
            elif text:
                actions.append(text)
        elif role == "tool" and text:
            name = call_names.get(str(message.get("tool_call_id") or ""), "unknown")
            actions.append(f"{name}: {text}")
            if re.search(
                r"\b(error|failed|exception|traceback|timeout|fatal)\b", text, re.I
            ):
                blockers.append(text[:500])

    def bullets(items: list[str], limit: int = 10) -> str:
        unique = list(dict.fromkeys(item for item in items if item))
        return "\n".join(f"- {item}" for item in unique[:limit]) or "None."

    task = f"User asked: {users[-1]!r}" if users else (
        "None. This session contains no user-authored turns."
    )
    previous = (
        "\n\n## Previous Summary Snapshot\n" + redactor(previous_summary[:3_000])
        if previous_summary
        else ""
    )
    body = f"""## Historical Task Snapshot
{task}

## Goal
Recovered locally because summary generation was unavailable.{previous}

## Constraints & Preferences
- This fallback is deterministic and may be incomplete.
- Verify repository and runtime state before relying on omitted details.

## Completed Actions
{bullets(actions, 12)}

## Active State
Unknown; inspect current state.

## Historical In-Progress State
Unknown; use protected recent messages as authoritative.

## Blocked
{bullets(blockers, 5)}

## Key Decisions
None recoverable.

## Resolved Questions
None recoverable.

## Historical Pending User Asks
None recoverable.

## Relevant Files
{bullets(files, 12)}

## Historical Remaining Work
Continue only from the latest protected user message.

## Last Dropped Turns
{bullets(recent, 8)}

## Critical Context
Fallback covered {len(messages)} compacted message(s). Reason: {reason or "unknown"}."""
    result = normalize_summary(redactor(body.strip()))
    if len(result) > max_chars:
        result = result[: max(max_chars - 32, 0)].rstrip() + "\n...[fallback truncated]"
    return result
