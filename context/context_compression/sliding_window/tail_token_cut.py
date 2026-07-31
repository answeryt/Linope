"""Token-budget tail cut with caller-injected policies."""

from collections.abc import Callable
from typing import Any


Message = dict[str, Any]
TokenEstimator = Callable[[Message], int]
BoundaryAligner = Callable[[list[Message], int], int]
TailAnchor = Callable[[list[Message], int, int], int]
LastNUsersAnchor = Callable[[list[Message], int, int, int], int]


def find_tail_cut_by_tokens(
    messages: list[Message],
    head_end: int,
    *,
    token_budget: int,
    protect_last_n: int,
    estimate_message_tokens: TokenEstimator,
    align_boundary_backward: BoundaryAligner,
    align_boundary_forward: BoundaryAligner,
    ensure_last_user_message_in_tail: TailAnchor,
    ensure_last_assistant_message_in_tail: TailAnchor,
    min_tail_user_messages: int = 1,
    ensure_last_n_user_messages_in_tail: LastNUsersAnchor | None = None,
    max_tail_message_floor: int = 8,
) -> int:
    """Return the protected-tail start under a token budget.

    The estimator is mandatory and supplied by the caller; this plugin does not
    implement token counting. The budget is primary. A bounded message-count
    floor protects a short recent run, and budget may exceed by up to 1.5x to
    avoid cutting inside an oversized message. If that floor itself exceeds the
    soft ceiling, the cut is forced after the head so compression can progress.

    Tool-group aligners and continuity anchors are also injected, keeping this
    file independent while retaining the historical ordering:
    backward alignment -> last user -> last assistant -> optional last-N users
    -> progress floor -> forward alignment.
    """
    count = len(messages)
    available_tail = max(0, count - head_end - 1)
    min_tail_floor = max(
        3,
        min(protect_last_n, max_tail_message_floor),
    )
    # Leave at least two non-head messages available to summarize on short
    # transcripts; otherwise a tiny replacement summary saves no messages.
    compressible_tail_cap = max(3, available_tail - 2)
    min_tail = (
        min(min_tail_floor, compressible_tail_cap, available_tail)
        if available_tail > 1
        else 0
    )
    soft_ceiling = int(token_budget * 1.5)
    accumulated = 0
    cut_index = count

    for index in range(count - 1, head_end - 1, -1):
        message_tokens = estimate_message_tokens(messages[index])
        if (
            accumulated + message_tokens > soft_ceiling
            and (count - index) >= min_tail
        ):
            break
        accumulated += message_tokens
        cut_index = index

    # If the full region fits the inflated ceiling, re-walk with the raw budget.
    # Otherwise the anchor/floor guards can repeatedly produce a no-op (#40803).
    if (
        cut_index <= head_end
        and accumulated <= soft_ceiling
        and accumulated > 0
    ):
        raw_accumulated = 0
        for index in range(count - 1, head_end - 1, -1):
            message_tokens = estimate_message_tokens(messages[index])
            if (
                raw_accumulated + message_tokens > token_budget
                and (count - index) >= min_tail
            ):
                cut_index = index
                break
            raw_accumulated += message_tokens
            cut_index = index

    fallback_cut = count - min_tail
    cut_index = min(cut_index, fallback_cut)

    # Force a meaningful middle region when the budget would protect everything.
    if cut_index <= head_end:
        cut_index = max(fallback_cut, head_end + 1)

    cut_index = align_boundary_backward(messages, cut_index)
    cut_index = ensure_last_user_message_in_tail(
        messages,
        cut_index,
        head_end,
    )
    cut_index = ensure_last_assistant_message_in_tail(
        messages,
        cut_index,
        head_end,
    )

    if (
        isinstance(min_tail_user_messages, int)
        and not isinstance(min_tail_user_messages, bool)
        and min_tail_user_messages > 1
        and ensure_last_n_user_messages_in_tail is not None
    ):
        cut_index = ensure_last_n_user_messages_in_tail(
            messages,
            cut_index,
            head_end,
            min_tail_user_messages,
        )

    # The progress floor may land inside a tool group. Re-align FORWARD, never
    # backward (which would return the floor's message), so the entire group is
    # summarized together instead of leaving orphan results in the tail.
    return align_boundary_forward(
        messages,
        max(cut_index, head_end + 1),
    )
