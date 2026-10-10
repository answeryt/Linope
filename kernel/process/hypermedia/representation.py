"""A resource handed to an agent: a few facts plus any number of links."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from kernel.process.hypermedia.link import Link


@dataclass(frozen=True)
class Representation:
    """One document. Links name other resources; they do not include those bodies."""

    facts: Mapping[str, Any]
    links: tuple[Link, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.links, tuple):
            object.__setattr__(self, "links", tuple(self.links))
        for link in self.links:
            if not isinstance(link, Link):
                raise TypeError("representation links must be Link values")
        object.__setattr__(self, "facts", dict(self.facts))
