"""Estimate tokens for text that is about to be sent. Stored rows are not scanned."""

from __future__ import annotations


def estimate_tokens(text: object) -> int:
    """A stable budget estimate. Provider billing can differ."""

    body = text if isinstance(text, str) else ""
    if not body:
        return 0
    return max(1, (len(body) + 3) // 4)


def count_texts(texts: list[object]) -> int:
    return sum(estimate_tokens(text) for text in texts)
