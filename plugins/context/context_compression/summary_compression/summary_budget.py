"""Summary output-budget policy with host-supplied token estimation."""

from collections.abc import Callable
from typing import Any


def compute_summary_budget(
    messages: list[dict[str, Any]],
    estimator: Callable[[list[dict[str, Any]]], int],
    *,
    minimum: int = 2_000,
    maximum: int = 10_000,
    ratio: float = 0.20,
) -> int:
    """Return a bounded summary target; token counting belongs to the host."""
    if minimum < 0 or maximum < minimum:
        raise ValueError("expected 0 <= minimum <= maximum")
    if not 0 <= ratio <= 1:
        raise ValueError("ratio must be between 0 and 1")
    estimated = estimator(messages)
    if isinstance(estimated, bool) or not isinstance(estimated, int):
        raise TypeError("estimator must return an integer")
    return max(minimum, min(int(max(estimated, 0) * ratio), maximum))
