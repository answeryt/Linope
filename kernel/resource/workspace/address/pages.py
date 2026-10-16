"""File pages mapped by one workspace handle.

Page states stay in ``kernel.resource.memory``. No handle means an empty space.
"""

from __future__ import annotations

from collections.abc import Sequence

from kernel.resource.memory.page import Page


def mapped_pages(handle: str | None, pairs: Sequence[tuple[object, object]]) -> tuple[Page, ...]:
    """Pages whose link carries this handle. An empty handle maps nothing."""
    if not handle:
        return ()
    found: list[Page] = []
    for page, link in pairs:
        if str(getattr(link, "handle", "") or "") != handle:
            continue
        if isinstance(page, Page):
            found.append(page)
    return tuple(found)
