"""Lossless, tail-agnostic deduplication of tool results."""

from __future__ import annotations

import hashlib
from typing import Any


DUPLICATE_MARKER = "[Duplicate tool output — same content as a more recent call]"


def deduplicate_tool_results(
    messages: list[dict[str, Any]],
    *,
    min_chars: int = 200,
    marker: str = DUPLICATE_MARKER,
) -> list[dict[str, Any]]:
    """Keep the newest full copy of each identical string tool result."""
    seen: set[str] = set()
    result = list(messages)
    changed = False
    for index in range(len(messages) - 1, -1, -1):
        message = messages[index]
        if message.get("role") != "tool":
            continue
        content = message.get("content")
        if not isinstance(content, str) or len(content) < min_chars:
            continue
        digest = hashlib.sha256(content.encode("utf-8", errors="replace")).hexdigest()
        if digest not in seen:
            seen.add(digest)
            continue
        result[index] = {**message, "content": marker}
        changed = True
    return result if changed else messages
