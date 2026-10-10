"""One hypermedia link: a relation and the resource it points at."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Link:
    """A pointer carried by a representation. The handle is the right to follow it."""

    relation: str
    resource_id: str
    handle: str = ""

    def __post_init__(self) -> None:
        if not self.relation:
            raise ValueError("link relation is required")
        if not self.resource_id:
            raise ValueError("link resource_id is required")

    def can_follow(self) -> bool:
        """A link with no handle cannot be walked."""
        return bool(self.handle)
