"""Find, strip, and rehydrate compaction handoffs."""

from collections.abc import Callable
from typing import Any


SUMMARY_METADATA_KEY = "_compressed_summary"
SUMMARY_HAS_USER_KEY = "_compressed_summary_has_user_turn"
SUMMARY_END_MARKER = (
    "--- END OF CONTEXT SUMMARY — respond to the message below, not the "
    "summary above ---"
)
MERGED_PRIOR_HEADER = "[PRIOR CONTEXT — for reference only; not a new message]"
MERGED_SUMMARY_DELIMITER = "[END OF PRIOR CONTEXT — COMPACTION SUMMARY BELOW]"


def find_handoffs(
    messages: list[dict[str, Any]],
    start: int,
    end: int,
    *,
    classify_content: Callable[[Any], str | None],
    strip_summary: Callable[[str], str],
    content_text: Callable[[Any], str],
) -> list[tuple[int, str]]:
    hits: list[tuple[int, str]] = []
    for index in range(max(start, 0), min(end, len(messages))):
        message = messages[index]
        if message.get(SUMMARY_METADATA_KEY) or classify_content(
            message.get("content")
        ):
            hits.append(
                (index, strip_summary(content_text(message.get("content"))))
            )
    return hits


def strip_handoff_message(
    message: dict[str, Any],
    *,
    classify_content: Callable[[Any], str | None],
) -> dict[str, Any] | None:
    """Remove stale summary material while retaining merged live content."""
    content = message.get("content")
    if not message.get(SUMMARY_METADATA_KEY) and not classify_content(content):
        return message.copy()

    if isinstance(content, str):
        if MERGED_SUMMARY_DELIMITER in content:
            prior = content.split(MERGED_SUMMARY_DELIMITER, 1)[0].strip()
            if prior.startswith(MERGED_PRIOR_HEADER):
                prior = prior[len(MERGED_PRIOR_HEADER):].lstrip()
            if prior:
                result = message.copy()
                result["content"] = prior
                result.pop(SUMMARY_METADATA_KEY, None)
                result.pop(SUMMARY_HAS_USER_KEY, None)
                return result
        marker_index = content.find(SUMMARY_END_MARKER)
        if marker_index >= 0:
            remainder = content[marker_index + len(SUMMARY_END_MARKER):].lstrip()
            if remainder:
                result = message.copy()
                result["content"] = remainder
                result.pop(SUMMARY_METADATA_KEY, None)
                result.pop(SUMMARY_HAS_USER_KEY, None)
                return result
        return None

    if isinstance(content, list):
        before: list[Any] = []
        found = False
        for item in content:
            text = item if isinstance(item, str) else (
                item.get("text") if isinstance(item, dict) else None
            )
            if isinstance(text, str) and MERGED_SUMMARY_DELIMITER in text:
                leading = text.split(MERGED_SUMMARY_DELIMITER, 1)[0]
                if leading.strip():
                    copied = item.copy() if isinstance(item, dict) else leading
                    if isinstance(copied, dict):
                        copied["text"] = leading
                    before.append(copied)
                found = True
                break
            before.append(item.copy() if isinstance(item, dict) else item)
        if found and before:
            first_text = before[0] if isinstance(before[0], str) else (
                before[0].get("text") if isinstance(before[0], dict) else None
            )
            if isinstance(first_text, str) and first_text.lstrip().startswith(
                MERGED_PRIOR_HEADER
            ):
                clean = first_text.lstrip()[len(MERGED_PRIOR_HEADER):].lstrip()
                if clean:
                    if isinstance(before[0], dict):
                        before[0]["text"] = clean
                    else:
                        before[0] = clean
                else:
                    before.pop(0)
            if before:
                result = message.copy()
                result["content"] = before
                result.pop(SUMMARY_METADATA_KEY, None)
                result.pop(SUMMARY_HAS_USER_KEY, None)
                return result
    return None


def rehydrate_handoffs(
    messages: list[dict[str, Any]],
    *,
    start: int,
    end: int,
    classify_content: Callable[[Any], str | None],
    strip_summary: Callable[[str], str],
    content_text: Callable[[Any], str],
    real_user_present: bool,
) -> dict[str, Any]:
    """Return rehydration data; the host decides whether and where to apply it."""
    hits = find_handoffs(
        messages,
        start,
        end,
        classify_content=classify_content,
        strip_summary=strip_summary,
        content_text=content_text,
    )
    bodies = [body for _, body in hits if body]
    newest = messages[hits[-1][0]] if hits else {}
    provenance = newest.get(SUMMARY_HAS_USER_KEY)
    if real_user_present:
        has_user = True
    elif isinstance(provenance, bool):
        has_user = provenance
    else:
        has_user = not any(
            "None. This session contains no user-authored turns." in body
            for body in bodies
        )
    return {
        "hits": hits,
        "indices": {index for index, _ in hits},
        "previous_summary": "\n\n".join(bodies) or None,
        "has_user_turn": has_user,
    }
