"""Last-N real actionable-user tail anchor."""

from collections.abc import Callable
from typing import Any


Message = dict[str, Any]
MessagePredicate = Callable[[Message], bool]
SingleUserAnchor = Callable[[list[Message], int, int], int]


def ensure_last_n_user_messages_in_tail(
    messages: list[Message],
    cut_index: int,
    head_end: int,
    count: int,
    *,
    is_actionable_user_turn: MessagePredicate,
    is_synthetic_compression_user_turn: MessagePredicate,
    ensure_last_user_message_in_tail: SingleUserAnchor,
) -> int:
    """Guarantee the last N real actionable users are in the protected tail.

    Blank echoes, compaction handoffs, continuation markers, and todo snapshots
    must not consume a slot. A user row is already a clean boundary, so backward
    tool-group alignment is intentionally not performed.

    For ``count <= 1``, the injected historical single-user anchor is used for
    regression-compatible causal-coupling behavior.
    """
    if count <= 1:
        return ensure_last_user_message_in_tail(messages, cut_index, head_end)

    user_indices: list[int] = []
    for index in range(len(messages) - 1, head_end - 1, -1):
        message = messages[index]
        if (
            is_actionable_user_turn(message)
            and not is_synthetic_compression_user_turn(message)
        ):
            user_indices.append(index)

    if not user_indices:
        return cut_index
    target_index = (
        user_indices[-1]
        if len(user_indices) < count
        else user_indices[count - 1]
    )
    if target_index >= cut_index:
        return cut_index
    return max(target_index, head_end + 1)
