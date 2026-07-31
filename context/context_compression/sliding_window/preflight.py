"""Read-only preflight for a sliding-window compression pass."""

from collections.abc import Callable
from typing import Any


Message = dict[str, Any]
HeadSizer = Callable[[list[Message]], int]
BoundaryAligner = Callable[[list[Message], int], int]
TailCutFinder = Callable[[list[Message], int], int]


def has_compressible_window(
    messages: list[Message],
    *,
    protect_head_size: HeadSizer,
    align_boundary_forward: BoundaryAligner,
    find_tail_cut_by_tokens: TailCutFinder,
) -> bool:
    """Return whether a non-empty middle region can be compacted.

    All policy functions are injected so this preflight stays side-effect free
    and independent of token, summary, and host implementations.
    """
    compress_start = align_boundary_forward(
        messages,
        protect_head_size(messages),
    )
    compress_end = find_tail_cut_by_tokens(messages, compress_start)
    return compress_start < compress_end
