"""Long-term context pages."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class PageState(StrEnum):
    RESIDENT = "resident"
    PINNED = "pinned"
    SWAPPED = "swapped"


@dataclass(frozen=True)
class Page:
    address: str
    size: int
    state: PageState = PageState.RESIDENT

    def __post_init__(self) -> None:
        if not self.address:
            raise ValueError("page address is required")
        if self.size < 0:
            raise ValueError("page size cannot be negative")

    def occupies_window(self) -> bool:
        return self.state is not PageState.SWAPPED

    def with_state(self, state: PageState) -> "Page":
        return Page(address=self.address, size=self.size, state=state)


def page_for_target(resource_id: str, size: int) -> Page:
    return Page(address=resource_id, size=size)
