"""HTTP resource URI formatting and parsing for Linope."""

from __future__ import annotations

from urllib.parse import quote, unquote, urlsplit

from kernel.hypermedia.link import Link
from kernel.resource.store.network import host_allowed

_RESOURCE_PREFIX = "/resources/"


def resource_uri(link: Link, base_url: str) -> str:
    """Build the public HTTP URI for a resource link."""
    if not link.handle:
        raise ValueError("a resource URI requires a link handle")
    parts = urlsplit(base_url.rstrip("/"))
    if parts.scheme not in {"http", "https"}:
        raise ValueError("resource base URL must use HTTP or HTTPS")
    if not parts.netloc:
        raise ValueError("resource base URL must include a host")
    return f"{parts.geturl().rstrip('/')}{_RESOURCE_PREFIX}{quote(link.handle, safe='')}"


def content_uri(link: Link, base_url: str) -> str:
    """Build the HTTP URI for the UTF-8 content of a resource."""
    return resource_uri(link, base_url) + "/content"


_PAGE_ACTIONS = frozenset({"pin", "swap", "admit", "compress"})


def action_uri(link: Link, base_url: str) -> str:
    """Build the HTTP URI for one page action on a resource."""
    if link.relation not in _PAGE_ACTIONS:
        raise ValueError("resource action is not one of pin, swap, admit, compress")
    return resource_uri(link, base_url) + "/" + link.relation


def tool_uri(link: Link, base_url: str) -> str:
    """Build the HTTP URI for one tool relation on a resource."""
    if not link.relation or link.relation in {"self", "content", *_PAGE_ACTIONS}:
        raise ValueError("tool URI requires a tool relation")
    return resource_uri(link, base_url) + "/tools/" + quote(link.relation, safe="")


def parse_resource_uri(value: str) -> str:
    """Return the opaque handle from a loopback resource URI."""
    parts = _parse_loopback(value)
    segments = [unquote(segment) for segment in parts.path.split("/") if segment]
    if len(segments) != 2 or segments[0] != "resources" or not segments[1]:
        raise ValueError("resource URI must have the form /resources/<id>")
    return _validate_handle(segments[1])


def parse_content_uri(value: str) -> str:
    """Return the opaque handle from a loopback content URI."""
    parts = _parse_loopback(value)
    segments = [unquote(segment) for segment in parts.path.split("/") if segment]
    if (
        len(segments) != 3
        or segments[0] != "resources"
        or segments[2] != "content"
        or not segments[1]
    ):
        raise ValueError("content URI must have the form /resources/<id>/content")
    return _validate_handle(segments[1])


def parse_action_uri(value: str) -> tuple[str, str]:
    """Return the opaque handle and page action from a loopback action URI."""
    parts = _parse_loopback(value)
    segments = [unquote(segment) for segment in parts.path.split("/") if segment]
    if (
        len(segments) != 3
        or segments[0] != "resources"
        or segments[2] not in _PAGE_ACTIONS
        or not segments[1]
    ):
        raise ValueError("action URI must have the form /resources/<id>/<action>")
    return _validate_handle(segments[1]), segments[2]


def parse_tool_uri(value: str) -> tuple[str, str]:
    """Return the opaque handle and tool name from a loopback tool URI."""
    parts = _parse_loopback(value)
    segments = [unquote(segment) for segment in parts.path.split("/") if segment]
    if (
        len(segments) != 4
        or segments[0] != "resources"
        or segments[2] != "tools"
        or not segments[1]
        or not segments[3]
    ):
        raise ValueError("tool URI must have the form /resources/<id>/tools/<name>")
    return _validate_handle(segments[1]), segments[3]


def _parse_loopback(value: str):
    parts = urlsplit(value)
    if parts.scheme not in {"http", "https"}:
        raise ValueError("resource URI must use HTTP or HTTPS")
    if not host_allowed(parts.hostname):
        raise ValueError("resource URI must target the configured Linope server")
    if parts.query or parts.fragment:
        raise ValueError("resource URI cannot contain a query or fragment")
    return parts


def _validate_handle(value: str) -> str:
    if not value or any(char not in "0123456789abcdefABCDEF" for char in value):
        raise ValueError("resource URI contains an invalid opaque id")
    return value
