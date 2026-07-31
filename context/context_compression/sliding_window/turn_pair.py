"""Causally complete user/assistant turn-pair boundary."""

from typing import Any


Message = dict[str, Any]


def find_turn_pair_end(messages: list[Message], user_index: int) -> int:
    """Return the index after the complete pair beginning at ``user_index``.

    A pair is ``user -> assistant -> zero-or-more tool results``. If no
    assistant immediately follows, only the user is covered. The returned index
    is the natural cut point that keeps the pair on one side of a boundary.
    """
    count = len(messages)
    index = user_index + 1
    if index >= count:
        return index
    if messages[index].get("role") != "assistant":
        return index
    index += 1
    while index < count and messages[index].get("role") == "tool":
        index += 1
    return index
