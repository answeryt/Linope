"""Count tokens for the raw texts already stored in one memory."""

from __future__ import annotations

from typing import Any

from kernel.resource.memory.state import text_contents


def count_state(model: str, state: dict[str, Any] | None) -> int:
    """A derived size. The stored rows stay text and metadata."""

    from kernel.calculate.measure import count_tokens

    total = 0
    for content in text_contents(state or {}):
        total += count_tokens(model, content)
    return total
