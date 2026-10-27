"""The model page: a projection of one pointer space plus the actions offered now.

Hypermedia only carries links. Which memory resource and which commands are on
the page is decided here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from kernel.hypermedia.handle import opaque
from kernel.hypermedia.link import Link
from kernel.hypermedia.memory_page import ANSWER, memory_page
from kernel.hypermedia.representation import Representation


@dataclass(frozen=True)
class CommandOffer:
    """One command line the page offers right now.

    ``start`` offers ``process start <capability>``. ``tool`` offers
    ``load tool <pid> -- `` for a tool that is up and sleeping. ``ask`` offers
    ``ask <pid> -- `` for a model that is up and sleeping.
    """

    way: str
    capability: str
    pid: int = 0
    schema: dict[str, Any] = field(default_factory=dict)

    @property
    def relation(self) -> str:
        return f"{self.way}:{self.capability}"

    @property
    def pointer(self) -> str:
        if self.way == "start":
            return f"process start {self.capability}"
        if self.way == "ask":
            return f"ask {self.pid} -- "
        return f"load tool {self.pid} -- "


def model_page(
    rows: list[dict[str, Any]],
    *,
    scope: str,
    seq: int,
    commands: tuple[CommandOffer, ...] = (),
    read: list[dict[str, Any]] | None = None,
) -> Representation:
    """Rows from the pointer space, then the memory resource and the offered actions."""

    page = memory_page(rows, scope=scope, seq=seq, read=read)
    facts = dict(page.facts)
    details = dict(facts.get("details") or {})
    links = list(page.links)
    for offer in commands:
        links.append(Link(offer.relation, offer.pointer, opaque(scope, seq, offer.pointer)))
        detail: dict[str, Any] = {"capability": offer.capability}
        if offer.way == "start" and offer.capability.startswith("model."):
            detail["with"] = "memory=<identity>"
        if offer.pid:
            detail["pid"] = offer.pid
        if offer.schema:
            detail["schema"] = offer.schema
        details[offer.relation] = detail
    if scope:
        links.append(Link("memory", scope, opaque(scope, seq, "memory")))
        details["memory"] = {"scope": scope}
    links.append(Link(ANSWER, ANSWER, opaque(scope, seq, ANSWER)))
    facts["details"] = details
    return Representation(facts, tuple(links))
