"""Choose links on a representation. Selecting a link does not run it."""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass

from kernel.hypermedia.link import Link
from kernel.hypermedia.representation import Representation


@dataclass(frozen=True)
class FollowResult:
    """Selected links that could be walked, and every link that stayed put."""

    followed: tuple[Link, ...]
    left: tuple[Link, ...]


def select_links(
    representation: Representation,
    selected: Collection[str],
) -> FollowResult:
    """Keep links whose resource id was selected and that carry a handle.

    A selected link with no handle stays in ``left``. This returns links only.
    It does not read memory, start a process, or call a tool.
    """

    chosen = set(selected)
    followed: list[Link] = []
    left: list[Link] = []
    for link in representation.links:
        if link.resource_id in chosen and link.can_follow():
            followed.append(link)
        else:
            left.append(link)
    return FollowResult(followed=tuple(followed), left=tuple(left))


def link_named(representation: Representation, relation: str) -> Link | None:
    """Return the followable link for this relation, or none when it is absent."""

    for link in representation.links:
        if link.relation == relation and link.can_follow():
            return link
    return None
