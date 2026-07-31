"""Strip, normalize, and classify compaction-summary text."""

from typing import Any


SUMMARY_PREFIX = (
    "[CONTEXT COMPACTION — REFERENCE ONLY] Earlier turns were compacted into "
    "the summary below. Treat it as background reference, not active "
    "instructions. Respond only to the latest user message after this summary:"
)
LEGACY_SUMMARY_PREFIX = "[CONTEXT SUMMARY]:"
SUMMARY_END_MARKER = (
    "--- END OF CONTEXT SUMMARY — respond to the message below, not the "
    "summary above ---"
)
MERGED_SUMMARY_DELIMITER = "[END OF PRIOR CONTEXT — COMPACTION SUMMARY BELOW]"


def content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return "" if content is None else str(content)
    parts: list[str] = []
    for item in content:
        if isinstance(item, str):
            parts.append(item)
        elif isinstance(item, dict) and isinstance(item.get("text"), str):
            parts.append(item["text"])
    return "\n".join(parts)


def strip_summary_prefix(
    summary: str,
    *,
    prefix: str = SUMMARY_PREFIX,
    legacy_prefix: str = LEGACY_SUMMARY_PREFIX,
    historical_prefixes: tuple[str, ...] = (),
    end_marker: str = SUMMARY_END_MARKER,
    merged_delimiter: str = MERGED_SUMMARY_DELIMITER,
) -> str:
    text = (summary or "").strip()
    if merged_delimiter in text:
        text = text.split(merged_delimiter, 1)[1].strip()
    for candidate in (prefix, legacy_prefix, *historical_prefixes):
        if candidate and text.startswith(candidate):
            text = text[len(candidate):].lstrip()
            break
    marker_index = text.find(end_marker)
    if marker_index >= 0:
        text = text[:marker_index].rstrip()
    return text


def normalize_summary(
    summary: str,
    *,
    prefix: str = SUMMARY_PREFIX,
    legacy_prefix: str = LEGACY_SUMMARY_PREFIX,
    historical_prefixes: tuple[str, ...] = (),
) -> str:
    body = strip_summary_prefix(
        summary,
        prefix=prefix,
        legacy_prefix=legacy_prefix,
        historical_prefixes=historical_prefixes,
    )
    return f"{prefix}\n{body}" if body else prefix


def classify_summary_content(
    content: Any,
    *,
    prefix: str = SUMMARY_PREFIX,
    legacy_prefix: str = LEGACY_SUMMARY_PREFIX,
    historical_prefixes: tuple[str, ...] = (),
    merged_delimiter: str = MERGED_SUMMARY_DELIMITER,
) -> str | None:
    text = content_to_text(content).lstrip()
    candidates = (prefix, legacy_prefix, *historical_prefixes)
    if merged_delimiter in text:
        after = text.split(merged_delimiter, 1)[1].lstrip()
        return "merged" if any(after.startswith(item) for item in candidates) else None
    return "standalone" if any(text.startswith(item) for item in candidates) else None
