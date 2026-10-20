"""Opaque local resource URI formatting and parsing."""

from __future__ import annotations

from urllib.parse import quote, unquote, urlsplit

from kernel.hypermedia.link import Link

_RESOURCE_PREFIX = "/resources/"
_PAGE_ACTIONS = frozenset({"pin", "swap", "admit"})
_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


def resource_uri(link: Link, base_url: str) -> str:
    if not link.handle:
        raise ValueError("a resource URI requires a link handle")
    parts = urlsplit(base_url.rstrip("/"))
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        raise ValueError("resource base URL must use HTTP or HTTPS")
    return f"{parts.geturl().rstrip('/')}{_RESOURCE_PREFIX}{quote(link.handle, safe='')}"


def content_uri(link: Link, base_url: str) -> str:
    return resource_uri(link, base_url) + "/content"


def action_uri(link: Link, base_url: str) -> str:
    if link.relation not in _PAGE_ACTIONS:
        raise ValueError("resource action must be pin, swap, or admit")
    return resource_uri(link, base_url) + "/" + link.relation


def parse_resource_uri(value: str) -> str:
    parts = _parse_local(value)
    segments = _segments(parts.path)
    if len(segments) != 2 or segments[0] != "resources":
        raise ValueError("resource URI must have the form /resources/<id>")
    return _validate_handle(segments[1])


def parse_content_uri(value: str) -> str:
    parts = _parse_local(value)
    segments = _segments(parts.path)
    if len(segments) != 3 or segments[:2] != ["resources", segments[1]]:
        raise ValueError("content URI must have the form /resources/<id>/content")
    if segments[2] != "content":
        raise ValueError("content URI must have the form /resources/<id>/content")
    return _validate_handle(segments[1])


def parse_action_uri(value: str) -> tuple[str, str]:
    parts = _parse_local(value)
    segments = _segments(parts.path)
    if len(segments) != 3 or segments[0] != "resources":
        raise ValueError("action URI must have the form /resources/<id>/<action>")
    if segments[2] not in _PAGE_ACTIONS:
        raise ValueError("resource action must be pin, swap, or admit")
    return _validate_handle(segments[1]), segments[2]


def _parse_local(value: str):
    parts = urlsplit(value)
    if parts.scheme not in {"http", "https"}:
        raise ValueError("resource URI must use HTTP or HTTPS")
    if parts.hostname not in _LOOPBACK_HOSTS:
        raise ValueError("resource URI must target the local Linope server")
    if parts.query or parts.fragment:
        raise ValueError("resource URI cannot contain a query or fragment")
    return parts


def _segments(path: str) -> list[str]:
    return [unquote(segment) for segment in path.split("/") if segment]


def _validate_handle(value: str) -> str:
    if not value or any(char not in "0123456789abcdefABCDEF" for char in value):
        raise ValueError("resource URI contains an invalid opaque id")
    return value
