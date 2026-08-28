"""Blank-echo and actionable-user predicates."""

from collections.abc import Callable
from typing import Any


Message = dict[str, Any]
MessagePredicate = Callable[[Message], bool]
ContentPredicate = Callable[[Any], bool]


def is_blank_user_turn(
    message: Message,
    *,
    has_compressed_summary_metadata: MessagePredicate,
    is_context_summary_content: ContentPredicate,
) -> bool:
    """Return whether a message is an empty, non-summary user-role echo."""
    if not isinstance(message, dict) or message.get("role") != "user":
        return False
    if has_compressed_summary_metadata(message):
        return False
    content = message.get("content")
    if is_context_summary_content(content):
        return False
    if content is None or (isinstance(content, str) and not content.strip()):
        return True
    if not isinstance(content, list):
        return False
    if not content:
        return True
    for part in content:
        if isinstance(part, str):
            if part.strip():
                return False
            continue
        if isinstance(part, dict) and part.get("type") in {"text", "input_text"}:
            text = part.get("text")
            if isinstance(text, str) and not text.strip():
                continue
        # Images, audio, and unknown structured blocks are user input.
        return False
    return True


def is_actionable_user_turn(
    message: Message,
    *,
    has_compressed_summary_metadata: MessagePredicate,
    is_context_summary_content: ContentPredicate,
) -> bool:
    """Return whether a message contains user input worth anchoring."""
    if not isinstance(message, dict) or message.get("role") != "user":
        return False
    if has_compressed_summary_metadata(message):
        return False
    content = message.get("content")
    if is_context_summary_content(content):
        return False
    return not is_blank_user_turn(
        message,
        has_compressed_summary_metadata=has_compressed_summary_metadata,
        is_context_summary_content=is_context_summary_content,
    )


def blank_echo_indices_after(
    messages: list[Message],
    user_index: int,
    *,
    is_blank_user: Callable[[Message], bool],
) -> set[int]:
    """Return contiguous blank echoes safe to remove after a user event.

    A blank user row is removable only when an assistant turn immediately
    follows the run. Otherwise it may be an intentional alternation placeholder
    for a transcript still being assembled.
    """
    indices: set[int] = set()
    if user_index < 0:
        return indices
    index = user_index + 1
    while index < len(messages) and is_blank_user(messages[index]):
        indices.add(index)
        index += 1
    if not indices or index >= len(messages):
        return set()
    return indices if messages[index].get("role") == "assistant" else set()
