"""The current page for one capability process."""

from __future__ import annotations

from typing import Any

from kernel.hypermedia.handle import opaque
from kernel.hypermedia.link import Link
from kernel.hypermedia.representation import Representation
from kernel.communication.address import address_scope


def process_page(
    record: Any,
    activity: str = "",
    counterpart: str = "",
    way: str = "",
    shares: tuple[str, ...] = (),
) -> Representation:
    """Facts say what it is doing. Links are only the steps allowed right now."""
    closed = str(getattr(getattr(record, "status", ""), "value", record.status)) == "closed"
    state = "closed" if closed else (activity or "sleeping")
    pid = str(int(record.pid))
    links = [Link("self", pid, pid)]
    if state == "with" and counterpart:
        links.append(Link("with", counterpart, counterpart))
    if state == "sleeping":
        links.append(Link("stop", pid, opaque("stop", pid, getattr(record, "started", "") or "")))
    for partner in shares:
        if partner and partner != pid:
            links.append(Link("share", partner, partner))
    scope = address_scope(getattr(record, "leases", ()) or ())
    if scope:
        links.append(Link("memory", scope, scope))
    facts = {
        "activity": state,
        "capability_id": str(record.capability_id),
        "pid": int(record.pid),
    }
    if state == "with":
        facts["way"] = way
    return Representation(facts, tuple(links))


def page_document(representation: Representation) -> dict[str, Any]:
    """The page as plain facts and links, without an HTTP address."""
    return {
        "facts": dict(representation.facts),
        "links": [
            {"rel": link.relation, "resource": link.resource_id}
            for link in representation.links
        ],
    }
