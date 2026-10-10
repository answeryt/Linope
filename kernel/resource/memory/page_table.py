"""Immutable page table for one context."""

from __future__ import annotations

from dataclasses import dataclass

from kernel.resource.memory.page import Page, PageState


@dataclass(frozen=True)
class PageTable:
    pages: tuple[Page, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.pages, tuple):
            object.__setattr__(self, "pages", tuple(self.pages))
        addresses = [page.address for page in self.pages]
        if len(addresses) != len(set(addresses)):
            raise ValueError("page addresses must be unique")

    def place(self, page: Page) -> "PageTable":
        if any(existing.address == page.address for existing in self.pages):
            raise ValueError(f"page already recorded: {page.address}")
        return PageTable(pages=(*self.pages, page))

    def put(self, page: Page) -> "PageTable":
        if any(existing.address == page.address for existing in self.pages):
            return PageTable(
                pages=tuple(
                    page if existing.address == page.address else existing
                    for existing in self.pages
                )
            )
        return PageTable(pages=(*self.pages, page))

    def with_state(self, address: str, state: PageState) -> "PageTable":
        return PageTable(
            pages=tuple(
                page.with_state(state) if page.address == address else page
                for page in self.pages
            )
        )

    def pin(self, address: str) -> "PageTable":
        self._require(address)
        return self.with_state(address, PageState.PINNED)

    def swap_out(self, address: str) -> "PageTable":
        page = self._require(address)
        if page.state is PageState.PINNED:
            raise ValueError(f"pinned page cannot be swapped out: {address}")
        return self.with_state(address, PageState.SWAPPED)

    def _require(self, address: str) -> Page:
        for page in self.pages:
            if page.address == address:
                return page
        raise KeyError(address)
