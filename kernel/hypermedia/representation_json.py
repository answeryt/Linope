"""JSON projection for the minimal local resource representation."""

from __future__ import annotations

from typing import Any

from kernel.hypermedia.link import Link
from kernel.hypermedia.representation import Representation
from kernel.hypermedia.uri import action_uri, content_uri, resource_uri

_GET_RELATIONS = frozenset({"self", "content"})
_PAGE_ACTIONS = frozenset({"pin", "swap", "admit"})
# Each kind of page owns the relations it may carry over HTTP.
RELATIONS: dict[str, frozenset[str]] = {
    "file": frozenset({"self", "content", "pin", "swap", "admit"}),
    "resource": frozenset({"self", "content", "pin", "swap", "admit"}),
}


def link_payload(link: Link, base_url: str, *, resource_type: str = "file") -> dict[str, str]:
    allowed = RELATIONS.get(resource_type)
    if allowed is None:
        raise ValueError(f"unsupported resource type: {resource_type}")
    if link.relation not in allowed:
        raise ValueError(f"unsupported {resource_type} relation: {link.relation}")
    if link.relation == "content":
        href = content_uri(link, base_url)
        media_type = "text/plain; charset=utf-8"
    elif link.relation in _PAGE_ACTIONS:
        href = action_uri(link, base_url)
        media_type = "application/json"
    elif link.relation == "self":
        href = resource_uri(link, base_url)
        media_type = "application/json"
    else:
        raise ValueError(f"unsupported resource relation: {link.relation}")
    return {
        "rel": link.relation,
        "href": href,
        "method": "GET" if link.relation in _GET_RELATIONS else "POST",
        "type": media_type,
    }


def representation_payload(
    representation: Representation,
    base_url: str,
    *,
    resource_type: str = "resource",
    resource_id: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = dict(representation.facts)
    payload["type"] = resource_type
    if resource_id is not None:
        payload["id"] = resource_id
    payload["_links"] = {
        link.relation: link_payload(link, base_url, resource_type=resource_type)
        for link in representation.links
    }
    return payload


def links_for_state(path: str, handle: str, state: str) -> tuple[Link, ...]:
    self_link = Link(relation="self", resource_id=path, handle=handle)
    if state == "swapped":
        return (self_link, Link(relation="admit", resource_id=path, handle=handle))
    if state == "pinned":
        return (self_link, Link(relation="content", resource_id=path, handle=handle))
    return (
        self_link,
        Link(relation="content", resource_id=path, handle=handle),
        Link(relation="pin", resource_id=path, handle=handle),
        Link(relation="swap", resource_id=path, handle=handle),
    )


def file_resource_payload(
    path: str,
    handle: str,
    state: str,
    base_url: str,
) -> dict[str, Any]:
    return representation_payload(
        Representation(
            facts={"state": state},
            links=links_for_state(path, handle, state),
        ),
        base_url,
        resource_type="file",
        resource_id=handle,
    )


def content_payload(
    *,
    path: str,
    handle: str,
    state: str,
    content: str,
    base_url: str,
) -> dict[str, Any]:
    payload = file_resource_payload(path, handle, state, base_url)
    payload["content"] = content
    return payload
