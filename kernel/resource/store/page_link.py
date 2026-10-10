"""A page pointer stored with a resource. It is not a hypermedia link."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PageLink:
    """Relation and handle kept beside a long-term page."""

    relation: str
    resource_id: str
    handle: str = ""

    def __post_init__(self) -> None:
        if not self.relation:
            raise ValueError("link relation is required")
        if not self.resource_id:
            raise ValueError("link resource_id is required")


def page_link_from(link: object) -> PageLink:
    """Copy the fields the resource ledger needs from any link-shaped object."""
    return PageLink(
        relation=str(getattr(link, "relation")),
        resource_id=str(getattr(link, "resource_id")),
        handle=str(getattr(link, "handle", "") or ""),
    )
