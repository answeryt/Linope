"""Recognition, protection and ghost-marker collection for skill_view."""

from __future__ import annotations

import json
import re
from typing import Any, Callable


DEFAULT_MARKER_PREFIX = "[SKILL_PRUNED:"


def skill_view_sites(messages: list[dict[str, Any]]) -> list[tuple[int, str, str]]:
    """Return ``(message index, skill name, call id)`` for valid calls."""
    sites: list[tuple[int, str, str]] = []
    for index, message in enumerate(messages):
        if message.get("role") != "assistant":
            continue
        for call in message.get("tool_calls") or []:
            if not isinstance(call, dict):
                continue
            function = call.get("function") if isinstance(call.get("function"), dict) else {}
            if function.get("name") != "skill_view":
                continue
            try:
                args = json.loads(function.get("arguments") or "")
            except (TypeError, ValueError):
                continue
            name = args.get("name") if isinstance(args, dict) else None
            if isinstance(name, str) and name:
                sites.append((index, name, str(call.get("call_id") or call.get("id") or "")))
    return sites


def protected_skill_names(
    messages: list[dict[str, Any]],
    *,
    protected_start: int,
    recent_messages: int = 10,
) -> set[str]:
    """Identify recently loaded, tail-resident or actively mentioned skills."""
    tail_start = max(0, protected_start)
    recent_start = max(0, len(messages) - max(0, recent_messages))
    user_text = "\n".join(
        str(message.get("content") or "").lower()
        for message in messages[tail_start:]
        if message.get("role") == "user" and isinstance(message.get("content"), str)
    )
    protected: set[str] = set()
    for index, name, _call_id in skill_view_sites(messages):
        key = name.lower()
        if index >= recent_start or index >= tail_start or key in user_text:
            protected.add(key)
    return protected


def collect_ghost_skill_markers(
    messages: list[dict[str, Any]],
    *,
    marker_factory: Callable[[str], str],
    raw_result_min_chars: int = 5000,
    marker_prefix: str = DEFAULT_MARKER_PREFIX,
    max_markers: int = 20,
) -> list[str]:
    """Collect canonical markers for demoted and soon-to-be-lost skill bodies."""
    by_call_id = {
        call_id: name
        for _index, name, call_id in skill_view_sites(messages)
        if call_id
    }
    names: list[str] = []
    marker_re = re.compile(
        re.escape(marker_prefix) + r"[^\]]*?reload with skill_view\(name='([^']+)'\)"
    )

    def add(name: str) -> None:
        if name and name not in names and len(names) < max_markers:
            names.append(name)

    for message in messages:
        content = message.get("content")
        text = content if isinstance(content, str) else ""
        for match in marker_re.finditer(text):
            add(match.group(1))
        if (
            message.get("role") == "tool"
            and isinstance(content, str)
            and len(content) > raw_result_min_chars
        ):
            add(by_call_id.get(str(message.get("tool_call_id") or ""), ""))
    return [marker_factory(name) for name in names]


def build_skill_protection_callback(
    messages: list[dict[str, Any]],
    *,
    protected_start: int,
    recent_messages: int = 10,
) -> Callable[[int, str, str, dict[str, Any]], bool]:
    """Build a callback suitable for a Host's demotion plugin invocation."""
    protected = protected_skill_names(
        messages,
        protected_start=protected_start,
        recent_messages=recent_messages,
    )

    def protect(_index: int, tool_name: str, arguments: str, _message: dict[str, Any]) -> bool:
        if tool_name != "skill_view":
            return False
        try:
            args = json.loads(arguments) if arguments else {}
        except (TypeError, ValueError):
            return False
        name = args.get("name") if isinstance(args, dict) else None
        return isinstance(name, str) and name.lower() in protected

    return protect
