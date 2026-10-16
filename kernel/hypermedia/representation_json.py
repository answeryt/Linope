"""Serialize Linope representations as HTTP HATEOAS JSON."""

from __future__ import annotations

from typing import Any

from kernel.hypermedia.link import Link
from kernel.hypermedia.representation import Representation
from kernel.hypermedia.tool_effect import ToolEffect, effect_for
from kernel.hypermedia.uri import action_uri, content_uri, resource_uri, tool_uri


_GET_RELATIONS = frozenset({"self", "content"})
_PAGE_ACTIONS = frozenset({"pin", "swap", "admit", "compress"})


def link_payload(link: Link, base_url: str) -> dict[str, str]:
    """Serialize one internal link with explicit HATEOAS fields."""
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
        href = tool_uri(link, base_url)
        media_type = "application/json"
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
    """Serialize facts and links without exposing internal file paths."""
    payload: dict[str, Any] = dict(representation.facts)
    payload["type"] = resource_type
    if resource_id is not None:
        payload["id"] = resource_id
    payload["_links"] = {
        link.relation: link_payload(link, base_url)
        for link in representation.links
    }
    return payload


def links_for_state(
    path: str,
    handle: str,
    state: str,
    *,
    compress: bool = False,
    tool_names: tuple[str, ...] = (),
) -> tuple[Link, ...]:
    """Menu for one page. Swapped pages cannot be read until they are admitted."""
    self_link = Link(relation="self", resource_id=path, handle=handle)
    if state == "swapped":
        links = [self_link, Link(relation="admit", resource_id=path, handle=handle)]
    elif state == "pinned":
        links = [self_link, Link(relation="content", resource_id=path, handle=handle)]
    else:
        links = [
            self_link,
            Link(relation="content", resource_id=path, handle=handle),
            Link(relation="pin", resource_id=path, handle=handle),
            Link(relation="swap", resource_id=path, handle=handle),
        ]
    if compress and state != "swapped":
        links.append(Link(relation="compress", resource_id=path, handle=handle))
    for name in tool_names:
        if name and effect_for(name) is not ToolEffect.SYSTEM:
            links.append(Link(relation=name, resource_id=path, handle=handle))
    return tuple(links)


def file_resource_payload(
    path: str,
    handle: str,
    state: str,
    base_url: str,
    *,
    compress: bool = False,
    tool_names: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Build the representation returned for one file resource."""
    representation = Representation(
        facts={"state": state},
        links=links_for_state(
            path,
            handle,
            state,
            compress=compress,
            tool_names=tool_names,
        ),
    )
    return representation_payload(
        representation,
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
    compress: bool = False,
    tool_names: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Build a JSON representation containing file content for RAG clients."""
    payload = file_resource_payload(
        path,
        handle,
        state,
        base_url,
        compress=compress,
        tool_names=tool_names,
    )
    payload["content"] = content
    return payload
