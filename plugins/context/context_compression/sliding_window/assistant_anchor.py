"""Latest user-visible assistant tail anchor."""

from collections.abc import Callable
from typing import Any


Message = dict[str, Any]
ContentPredicate = Callable[[Any], bool]
MessagePredicate = Callable[[Message], bool]
BoundaryAligner = Callable[[list[Message], int], int]


def find_last_assistant_message_index(
    messages: list[Message],
    head_end: int,
    *,
    is_context_summary_content: ContentPredicate,
    is_context_summary_message: MessagePredicate,
) -> int:
    """Return the latest user-visible assistant reply at/after ``head_end``.

    Prefer non-empty textual replies over tool-call-only assistant rows. Summary
    handoffs are internal continuity state and never qualify. If no visible
    reply exists, fall back to the newest non-summary assistant row.
    """
    last_any = -1
    for index in range(len(messages) - 1, head_end - 1, -1):
        message = messages[index]
        if (
            message.get("role") != "assistant"
            or is_context_summary_content(message.get("content"))
            or is_context_summary_message(message)
        ):
            continue
        if last_any < 0:
            last_any = index
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return index
        if isinstance(content, list):
            for part in content:
                if isinstance(part, dict):
                    text = part.get("text") or part.get("content")
                    if isinstance(text, str) and text.strip():
                        return index
    return last_any


def ensure_last_assistant_message_in_tail(
    messages: list[Message],
    cut_index: int,
    head_end: int,
    *,
    is_context_summary_content: ContentPredicate,
    is_context_summary_message: MessagePredicate,
    align_boundary_backward: BoundaryAligner,
) -> int:
    """Guarantee the latest visible assistant reply is in the protected tail.

    Re-align backward around a preceding tool group so anchoring a final reply
    cannot leave orphaned tool results in the tail.
    """
    last_assistant_index = find_last_assistant_message_index(
        messages,
        head_end,
        is_context_summary_content=is_context_summary_content,
        is_context_summary_message=is_context_summary_message,
    )
    if last_assistant_index < 0 or last_assistant_index >= cut_index:
        return cut_index
    new_cut = align_boundary_backward(messages, last_assistant_index)
    return max(new_cut, head_end + 1)
