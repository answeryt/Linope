"""Assemble a summary between protected transcript regions."""

from collections.abc import Callable
from typing import Any


SUMMARY_METADATA_KEY = "_compressed_summary"
SUMMARY_HAS_USER_KEY = "_compressed_summary_has_user_turn"
PERSISTENCE_KEY = "_db_persisted"
SUMMARY_END_MARKER = (
    "--- END OF CONTEXT SUMMARY — respond to the message below, not the "
    "summary above ---"
)
MERGED_PRIOR_HEADER = "[PRIOR CONTEXT — for reference only; not a new message]"
MERGED_SUMMARY_DELIMITER = "[END OF PRIOR CONTEXT — COMPACTION SUMMARY BELOW]"


def _append_text(content: Any, text: str, *, prepend: bool = False) -> Any:
    if isinstance(content, str):
        return text + content if prepend else content + text
    if isinstance(content, list):
        result = [item.copy() if isinstance(item, dict) else item for item in content]
        block = {"type": "text", "text": text}
        return [block, *result] if prepend else [*result, block]
    base = "" if content is None else str(content)
    return text + base if prepend else base + text


def assemble_compressed_transcript(
    head: list[dict[str, Any]],
    tail: list[dict[str, Any]],
    summary: str,
    *,
    has_user_turn: bool,
    strip_handoff: Callable[[dict[str, Any]], dict[str, Any] | None],
    drop_stale: Callable[[dict[str, Any]], None],
    system_note: str | None = None,
) -> list[dict[str, Any]]:
    """Insert or merge a handoff without introducing a role collision."""

    def fresh(message: dict[str, Any]) -> dict[str, Any]:
        copied = message.copy()
        copied.pop(PERSISTENCE_KEY, None)
        return copied

    clean_head: list[dict[str, Any]] = []
    for index, source in enumerate(head):
        message = fresh(source)
        if index == 0 and message.get("role") == "system" and system_note:
            content = message.get("content")
            text = content if isinstance(content, str) else str(content or "")
            if system_note not in text:
                message["content"] = _append_text(
                    content,
                    ("\n\n" if content else "") + system_note,
                )
                drop_stale(message)
        stripped = strip_handoff(message)
        if stripped is not None:
            clean_head.append(stripped)

    clean_tail: list[dict[str, Any]] = []
    for source in tail:
        stripped = strip_handoff(fresh(source))
        if stripped is not None:
            clean_tail.append(stripped)

    last_head_role = clean_head[-1].get("role", "user") if clean_head else "user"
    first_tail_role = clean_tail[0].get("role") if clean_tail else None
    force_user_leading = not clean_head or last_head_role == "system"
    if not force_user_leading:
        force_user_leading = not any(
            message.get("role") == "user" for message in clean_head + clean_tail
        )

    summary_role = (
        "user"
        if last_head_role in {"assistant", "tool"} or force_user_leading
        else "assistant"
    )
    merge_into_tail = False
    if first_tail_role is not None and summary_role == first_tail_role:
        flipped = "assistant" if summary_role == "user" else "user"
        if flipped != last_head_role and not force_user_leading:
            summary_role = flipped
        else:
            merge_into_tail = True

    metadata = {
        SUMMARY_METADATA_KEY: True,
        SUMMARY_HAS_USER_KEY: bool(has_user_turn),
    }
    result = clean_head
    if not merge_into_tail:
        result.append(
            {
                "role": summary_role,
                "content": summary + "\n\n" + SUMMARY_END_MARKER,
                **metadata,
            }
        )

    for index, message in enumerate(clean_tail):
        if merge_into_tail and index == 0:
            old_content = message.get("content", "")
            if force_user_leading and summary_role == "user":
                prefix = summary + "\n\n" + SUMMARY_END_MARKER + "\n\n"
                message["content"] = _append_text(
                    old_content, prefix, prepend=True
                )
            else:
                suffix = (
                    "\n\n"
                    + MERGED_SUMMARY_DELIMITER
                    + "\n\n"
                    + summary
                    + "\n\n"
                    + SUMMARY_END_MARKER
                )
                merged = _append_text(old_content, suffix)
                message["content"] = _append_text(
                    merged, MERGED_PRIOR_HEADER + "\n", prepend=True
                )
            message.update(metadata)
            drop_stale(message)
            merge_into_tail = False
        result.append(message)

    for message in result:
        message.pop(PERSISTENCE_KEY, None)
    return result
