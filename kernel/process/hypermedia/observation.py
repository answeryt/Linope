"""Carry a hypermedia representation in the existing mailbox.

Taking or claiming the message does not change the page. A later action
re-reads ``self`` and runs only a relation that is still on that menu.
"""

from __future__ import annotations

import json
from typing import Any
from urllib.request import Request, urlopen


def offered_href(representation: dict[str, Any], relation: str) -> str | None:
    """Return the href for one relation, or none when the menu omits it."""
    links = representation.get("_links")
    if not isinstance(links, dict):
        return None
    link = links.get(relation)
    if not isinstance(link, dict):
        return None
    href = link.get("href")
    if not isinstance(href, str) or not href:
        return None
    return href


def observation_body(representation: dict[str, Any]) -> dict[str, Any]:
    """Wrap one representation. The queued copy is for reading, not for acting."""
    href = offered_href(representation, "self")
    if href is None:
        raise ValueError("观察需要当前表示里的 self")
    return {
        "operation": "observe",
        "href": href,
        "representation": representation,
    }


def deliver_observation(
    channel: Any,
    process_id: str,
    representation: dict[str, Any],
    sender_id: str | None = None,
) -> str:
    """Submit one observation through a channel that already exists."""
    return channel.submit(process_id, observation_body(representation), sender_id)


def fetch_representation(href: str, *, timeout: float = 10) -> dict[str, Any]:
    """GET one resource representation as JSON."""
    request = Request(href, headers={"Accept": "application/json"})
    with urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("资源表示必须是 JSON 对象")
    return payload


def act_if_offered(
    href: str,
    relation: str,
    *,
    timeout: float = 10,
) -> dict[str, Any] | None:
    """Re-read the current menu, then follow ``relation`` only if it is listed.

    The returned document is the server's new representation. A missing
    relation leaves the page alone and returns none.
    """
    current = fetch_representation(href, timeout=timeout)
    target = offered_href(current, relation)
    if target is None:
        return None
    link = current["_links"][relation]
    method = str(link.get("method") or "GET").upper()
    if method == "GET":
        return fetch_representation(target, timeout=timeout)
    if method == "POST":
        return _post_representation(target, timeout=timeout)
    raise ValueError(f"不认识的方法: {method}")


def _post_representation(href: str, timeout: float) -> dict[str, Any]:
    request = Request(
        href,
        data=b"{}",
        method="POST",
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("资源表示必须是 JSON 对象")
    return payload
