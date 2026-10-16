"""One measured line, and a report made of those lines."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Line:
    """Used amount, optional ceiling, and unit for one resource kind."""

    kind: str
    used: int
    ceiling: int | None
    unit: str
    detail: tuple[tuple[str, int], ...] = ()

    def detail_of(self, key: str) -> int:
        """Extra number recorded beside the main used amount."""
        for name, value in self.detail:
            if name == key:
                return value
        return 0


@dataclass(frozen=True)
class Report:
    """The same result for the whole machine, one service, or one process."""

    scope: str
    lines: tuple[Line, ...]

    def line(self, kind: str) -> Line | None:
        """The line for this kind, when the scope has anything to say about it."""
        for item in self.lines:
            if item.kind == kind:
                return item
        return None
