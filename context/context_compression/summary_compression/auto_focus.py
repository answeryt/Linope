"""Derive a bounded focus hint from recent real user turns."""

from collections.abc import Callable
from typing import Any


def derive_auto_focus(
    messages: list[dict[str, Any]],
    *,
    is_real_user: Callable[[dict[str, Any]], bool],
    content_text: Callable[[Any], str],
    redactor: Callable[[str], str],
    max_turns: int = 3,
    turn_max_chars: int = 260,
    max_chars: int = 700,
) -> str | None:
    candidates: list[str] = []
    for message in reversed(messages):
        if message.get("role") != "user" or not is_real_user(message):
            continue
        text = " ".join(
            redactor(content_text(message.get("content"))).strip().split()
        )
        if not text:
            continue
        if len(text) > turn_max_chars:
            text = text[: max(turn_max_chars - 1, 0)].rstrip() + "…"
        candidates.append(text)
        if len(candidates) >= max_turns:
            break
    if not candidates:
        return None
    focus = "Recent user focus:\n" + "\n".join(
        f"- {item}" for item in reversed(candidates)
    )
    if len(focus) > max_chars:
        focus = focus[: max(max_chars - 1, 0)].rstrip() + "…"
    return focus
