"""Long-term pages created for files."""

from __future__ import annotations

from kernel.resource.memory.page import Page, PageState, page_for_target


def page_for_written_file(address: str, size: int, lasting: bool) -> Page:
    page = page_for_target(address, size)
    if lasting:
        return page.with_state(PageState.PINNED)
    return page
