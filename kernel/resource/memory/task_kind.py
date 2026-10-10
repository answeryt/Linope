"""Whether a task writes a long-term page."""

from __future__ import annotations

from enum import StrEnum


class TaskKind(StrEnum):
    FREE = "free"
    OCCUPY = "occupy"


def task_kind_for(*, followed: bool) -> TaskKind:
    return TaskKind.OCCUPY if followed else TaskKind.FREE
