"""The page a model process reads: its memory addresses, the commands it may run, and answer.

Rows of the current turn carry their words. Earlier rows only carry an address,
which the model may read back with a pointer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from kernel.hypermedia.handle import opaque
from kernel.hypermedia.link import Link
from kernel.hypermedia.representation import Representation

ANSWER = "answer"


@dataclass(frozen=True)
class CommandOffer:
    """One command line the page offers right now.

    ``start`` offers ``process start <capability>``. ``tool`` offers
    ``load tool <pid> -- `` for a process that is up and sleeping.
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
        return f"load tool {self.pid} -- "


def memory_page(
    rows: list[dict[str, Any]],
    *,
    scope: str,
    seq: int,
    commands: tuple[CommandOffer, ...] = (),
    read: list[dict[str, Any]] | None = None,
) -> Representation:
    """One page for this memory at this seq. Handles are bound to both."""
    turn = _turn_start(rows)
    shown: list[dict[str, Any]] = []
    links: list[Link] = []
    details: dict[str, dict[str, Any]] = {}
    for row in rows:
        address = str(row.get("address") or "")
        if not address:
            continue
        kind = str(row.get("kind") or "")
        links.append(Link(address, address, opaque(scope, seq, address)))
        details[address] = {"kind": kind}
        if kind == "system" or int(row.get("seq") or 0) < turn:
            continue
        item = {"address": address, "kind": kind, "content": str(row.get("content") or "")}
        if row.get("state"):
            item["state"] = str(row["state"])
        shown.append(item)
    for offer in commands:
        links.append(Link(offer.relation, offer.pointer, opaque(scope, seq, offer.pointer)))
        detail: dict[str, Any] = {"capability": offer.capability}
        if offer.pid:
            detail["pid"] = offer.pid
        if offer.schema:
            detail["schema"] = offer.schema
        details[offer.relation] = detail
    links.append(Link(ANSWER, ANSWER, opaque(scope, seq, ANSWER)))
    facts: dict[str, Any] = {
        "state": _page_state(rows),
        "seq": int(seq),
        "rows": shown,
        "details": details,
    }
    if read:
        facts["read"] = read
    return Representation(facts, tuple(links))


def page_document(page: Representation) -> dict[str, Any]:
    """The page as the model reads it: facts, then each link with its pointer."""
    facts = dict(page.facts)
    details = facts.pop("details", {}) or {}
    document: dict[str, Any] = {"state": facts.pop("state"), "seq": facts.pop("seq")}
    document.update(facts)
    document["_links"] = {
        link.relation: {"pointer": link.resource_id, "handle": link.handle, **details.get(link.relation, {})}
        for link in page.links
    }
    return document


def allowed_pointers(page: Representation) -> list[str]:
    return [link.resource_id for link in page.links]


def _turn_start(rows: list[dict[str, Any]]) -> int:
    """The seq of the newest user question. Rows from there on are this turn."""
    start = 0
    for row in rows:
        if str(row.get("kind") or "") == "user":
            start = max(start, int(row.get("seq") or 0))
    return start


def _page_state(rows: list[dict[str, Any]]) -> str:
    newest = max(rows, key=lambda row: int(row.get("seq") or 0), default=None)
    if newest is None:
        return "asked"
    return str(newest.get("state") or "asked")
