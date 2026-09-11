"""Latest actionable-user tail anchor."""

from collections.abc import Callable
from typing import Any


Message = dict[str, Any]
MessagePredicate = Callable[[Message], bool]
TurnPairEndFinder = Callable[[list[Message], int], int]


def find_last_user_message_index(
    messages: list[Message],
    head_end: int,
    *,
    is_actionable_user_turn: MessagePredicate,
    is_synthetic_compression_user_turn: MessagePredicate,
) -> int:
    """Return the latest real actionable user turn at/after ``head_end``."""
    for index in range(len(messages) - 1, head_end - 1, -1):
        message = messages[index]
        if (
            is_actionable_user_turn(message)
            and not is_synthetic_compression_user_turn(message)
        ):
            return index
    return -1


def ensure_last_user_message_in_tail(
    messages: list[Message],
    cut_index: int,
    head_end: int,
    *,
    is_actionable_user_turn: MessagePredicate,
    is_synthetic_compression_user_turn: MessagePredicate,
    find_turn_pair_end: TurnPairEndFinder,
) -> int:
    """Guarantee the most recent real user message is in the protected tail.

    A user row is already a clean boundary, so this intentionally does not
    align backward into a preceding assistant/tool group.

    Causal-coupling guard: if the head floor would push the cut past a user at
    ``head_end``, push forward to the complete pair end instead. This keeps an
    already-completed request from being summarized as a dangling pending ask.
    """
    last_user_index = find_last_user_message_index(
        messages,
        head_end,
        is_actionable_user_turn=is_actionable_user_turn,
        is_synthetic_compression_user_turn=is_synthetic_compression_user_turn,
    )
    if last_user_index < 0 or last_user_index >= cut_index:
        return cut_index

    adjusted = max(last_user_index, head_end + 1)
    if adjusted > last_user_index:
        pair_end = find_turn_pair_end(messages, last_user_index)
        return max(pair_end, head_end + 1)
    return adjusted
