"""A projection of memory rows. Commands and the answer link are added by the model page.

Rows of the current turn carry their words. Earlier rows only carry an address,
kind, and time. Entering one of those addresses still requires the process
pointer space.
"""

from __future__ import annotations

from typing import Any

from kernel.hypermedia.handle import opaque
from kernel.hypermedia.link import Link
from kernel.hypermedia.representation import Representation

ANSWER = "answer"


def memory_page(
    rows: list[dict[str, Any]],
    *,
    scope: str,
    seq: int,
    read: list[dict[str, Any]] | None = None,
) -> Representation:
    """Addresses this memory currently projects. This page does not grant them."""

    turn = _turn_start(rows)
    shown: list[dict[str, Any]] = []
    links: list[Link] = []
    details: dict[str, dict[str, Any]] = {}
    for row in rows:
        address = str(row.get("address") or "")
        if not address:
            continue
        kind = str(row.get("kind") or "")
        when = str(row.get("time") or "")
        links.append(Link(address, address, opaque(scope, seq, address)))
        details[address] = {"kind": kind, "time": when}
        if kind == "system" or int(row.get("seq") or 0) < turn:
            continue
        item = {"address": address, "kind": kind, "content": str(row.get("content") or ""), "time": when}
        if row.get("state"):
            item["state"] = str(row["state"])
        shown.append(item)
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
