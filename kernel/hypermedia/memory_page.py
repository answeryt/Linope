"""The rows this turn is showing. Older memory is not linked from the page.

Entering an address still requires the process pointer space. The model asks
for ``message/0`` itself; this page does not publish a directory of addresses.
"""

from __future__ import annotations

from typing import Any

from kernel.hypermedia.representation import Representation

ANSWER = "answer"


def memory_page(
    rows: list[dict[str, Any]],
    *,
    scope: str,
    seq: int,
    read: list[dict[str, Any]] | None = None,
    state: str | None = None,
) -> Representation:
    """Show only the rows the caller named for this request."""

    del scope
    shown = [_public(row) for row in (read if read is not None else rows)]
    facts: dict[str, Any] = {
        "state": state or _page_state(shown),
        "seq": int(seq),
        "rows": shown,
    }
    return Representation(facts, ())


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


def _public(row: dict[str, Any]) -> dict[str, Any]:
    item: dict[str, Any] = {
        "kind": str(row.get("kind") or ""),
        "content": str(row.get("content") or ""),
    }
    if row.get("address"):
        item["address"] = str(row["address"])
    if row.get("time"):
        item["time"] = str(row["time"])
    if row.get("state"):
        item["state"] = str(row["state"])
    return item


def _page_state(rows: list[dict[str, Any]]) -> str:
    newest = rows[-1] if rows else None
    if newest is None:
        return "asked"
    return str(newest.get("state") or "asked")
