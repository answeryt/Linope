"""Protected-head sizing with first-compaction decay.

This module is intentionally independent.  Summary recognition is supplied by
the caller because the sliding-window layer must not know summary formats.
"""

from collections.abc import Callable
from typing import Any


Message = dict[str, Any]
SummaryMessagePredicate = Callable[[Message], bool]


def restart_handoff_probe_bounds(
    messages: list[Message],
    protect_first_n: int,
    *,
    probe_extra_messages: int,
) -> tuple[int, int]:
    """Return the bounded transcript region that can indicate restart decay."""
    if not messages or protect_first_n <= 0:
        return 0, 0
    first_non_system = 1 if messages[0].get("role") == "system" else 0
    return first_non_system, min(
        len(messages),
        first_non_system + protect_first_n + probe_extra_messages,
    )


def effective_protect_first_n(
    messages: list[Message],
    protect_first_n: int,
    *,
    compression_count: int = 0,
    previous_summary: str = "",
    is_context_summary_message: SummaryMessagePredicate,
    probe_extra_messages: int,
) -> int:
    """Return ``protect_first_n`` decayed across compression cycles.

    ``protect_first_n`` keeps the first N non-system messages verbatim so the
    original task framing survives the FIRST compaction. Applying it on every
    pass fossilizes early turns. Once a summary exists, decay to zero; the
    system prompt remains protected separately.

    After a restart, decay is inferred only from the bounded resumed-head
    region. Summary-looking tail content must not decay first-pass protection.
    """
    if compression_count >= 1 or previous_summary:
        return 0
    if messages and protect_first_n > 0:
        start, end = restart_handoff_probe_bounds(
            messages,
            protect_first_n,
            probe_extra_messages=probe_extra_messages,
        )
        if any(is_context_summary_message(message) for message in messages[start:end]):
            return 0
    return protect_first_n


def protect_head_size(
    messages: list[Message],
    protect_first_n: int,
    *,
    compression_count: int = 0,
    previous_summary: str = "",
    is_context_summary_message: SummaryMessagePredicate,
    probe_extra_messages: int,
) -> int:
    """Return the total protected-head message count.

    ``protect_first_n`` means additional messages beyond the system prompt.
    The system prompt at index zero is always implicitly protected.
    """
    system_count = (
        1 if messages and messages[0].get("role") == "system" else 0
    )
    return system_count + effective_protect_first_n(
        messages,
        protect_first_n,
        compression_count=compression_count,
        previous_summary=previous_summary,
        is_context_summary_message=is_context_summary_message,
        probe_extra_messages=probe_extra_messages,
    )
