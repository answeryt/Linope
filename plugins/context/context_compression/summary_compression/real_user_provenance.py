"""Determine and validate real-user provenance with injected predicates."""

import re
from collections.abc import Callable
from typing import Any


NO_USER_TASK_SENTINEL = "None. This session contains no user-authored turns."
HISTORICAL_TASK_HEADING = "## Historical Task Snapshot"


def transcript_has_real_user(
    messages: list[dict[str, Any]],
    *,
    is_synthetic_user: Callable[[dict[str, Any]], bool],
) -> bool:
    return any(
        message.get("role") == "user" and not is_synthetic_user(message)
        for message in messages
    )


def validate_summary_provenance(summary: str, *, has_user_turn: bool) -> None:
    """Reject invented user attribution in zero-user transcripts."""
    if has_user_turn:
        return
    match = re.search(
        rf"(?ms)^{re.escape(HISTORICAL_TASK_HEADING)}\s*\n(.*?)(?=\n##\s|\Z)",
        summary,
    )
    snapshot = match.group(1).strip() if match else ""
    if snapshot != NO_USER_TASK_SENTINEL or re.search(
        r"\bUser\s+asked\s*:", summary, re.I
    ):
        raise ValueError("summary invented user attribution")
