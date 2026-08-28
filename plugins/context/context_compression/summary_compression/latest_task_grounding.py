"""Ground the historical task section in the newest real user turn."""

import re
from collections.abc import Callable
from typing import Any


HEADING = "## Historical Task Snapshot"
SECTION_RE = re.compile(
    rf"(?ms)^{re.escape(HEADING)}\s*\n.*?(?=^##\s|\Z)"
)


def latest_task_snapshot(
    messages: list[dict[str, Any]],
    *,
    is_real_user: Callable[[dict[str, Any]], bool],
    content_text: Callable[[Any], str],
    redactor: Callable[[str], str],
    max_chars: int = 1_400,
) -> str | None:
    for message in reversed(messages):
        if message.get("role") != "user" or not is_real_user(message):
            continue
        text = re.sub(
            r"\s+", " ", redactor(content_text(message.get("content"))).strip()
        )
        if not text:
            continue
        if len(text) > max_chars:
            text = text[: max(max_chars - 15, 0)].rstrip() + " ...[truncated]"
        return (
            f"User asked (deterministic, from compacted turns): {text!r}\n"
            "Historical only; newer protected-tail messages win."
        )
    return None


def ground_latest_task(
    summary: str,
    messages: list[dict[str, Any]],
    *,
    is_real_user: Callable[[dict[str, Any]], bool],
    content_text: Callable[[Any], str],
    redactor: Callable[[str], str],
) -> str:
    snapshot = latest_task_snapshot(
        messages,
        is_real_user=is_real_user,
        content_text=content_text,
        redactor=redactor,
    )
    if not snapshot:
        return summary
    replacement = f"{HEADING}\n{snapshot}\n\n"
    if SECTION_RE.search(summary):
        return SECTION_RE.sub(lambda _: replacement, summary, count=1).strip()
    return (replacement + summary).strip()
