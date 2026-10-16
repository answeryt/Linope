"""Durable HATEOAS representation recorded for one memory resource.

The link menu is chosen from ``state`` in ``kernel.hypermedia``.
A swapped representation keeps its address and is only a link, so its size
does not count toward the memory quantity.
"""

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
            raise ValueError("representation address is required")
        if self.size < 0:
            raise ValueError("representation size cannot be negative")

    def embedded(self) -> bool:
        """The body is in this representation. A swapped record is only a link."""
        return self.state is not PageState.SWAPPED

    def with_state(self, state: PageState) -> "Page":
        return Page(address=self.address, size=self.size, state=state)


def page_for_target(resource_id: str, size: int) -> Page:
    return Page(address=resource_id, size=size)
