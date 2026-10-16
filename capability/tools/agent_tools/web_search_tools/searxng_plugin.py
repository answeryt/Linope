# -*- coding: utf-8 -*-
"""Search the web through a SearXNG instance."""

from __future__ import annotations

import json
import os
import ssl
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, HTTPSHandler, Request, build_opener


PLUGIN_NAME = "searxng"
PLUGIN_VERSION = "1.0"
CARD = {"api_key_env": "SEARXNG_URL"}

TIMEOUT_SECONDS = 30

SEARXNG_SCHEMA: dict[str, Any] = {
    "name": "searxng",
    "description": "Search the web with a SearXNG instance. Returns titles, URLs, and descriptions.",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query.",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of results. Defaults to 5.",
                "minimum": 1,
                "maximum": 10,
                "default": 5,
            },
        },
        "required": ["query"],
    },
}


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def tool_schemas() -> list[dict[str, Any]]:
    return [SEARXNG_SCHEMA]


def load(kind, body, call_params=None):
    """Load one tool call. Argument shape stays in this plugin."""
    if kind != "tool":
        raise ValueError(f"这个进程不能装入 {kind}")
    if not isinstance(body, dict):
        raise TypeError("tool 的内容必须是映射")
    return dispatch(PLUGIN_NAME, body, **(call_params or {}))


def dispatch(name: str, arguments: dict[str, Any], **kwargs: Any) -> str:
    if name != PLUGIN_NAME:
        return _error(f"unknown tool: {name}")
    return searxng_search(
        str(arguments.get("query") or ""),
        limit=arguments.get("limit", 5),
    )


def searxng_search(query: str, limit: int = 5) -> str:
    """GET JSON results from the configured SearXNG instance."""
    query = query.strip()
    if not query:
        return _error("query must be a non-empty string")
    limit = _limit(limit)
    base = _secret(CARD["api_key_env"])
    if base is None:
        return _error(f"missing {CARD['api_key_env']}")
    if not base.startswith(("http://", "https://")):
        return _error("SEARXNG_URL must be an HTTP(S) URL")
    url = base.rstrip("/") + "/search?" + urlencode({"q": query, "format": "json"})
    payload, raw, error = _get(url, {"Accept": "application/json"})
    if error:
        return error
    web = []
    for index, item in enumerate(payload.get("results") or [], start=1):
        if not isinstance(item, dict):
            continue
        if len(web) >= limit:
            break
        page = str(item.get("url") or "")
        title = str(item.get("title") or "")
        if not page and not title:
            continue
        web.append(
            {
                "title": title,
                "url": page,
                "description": str(item.get("content") or ""),
                "position": index,
            }
        )
    _charge(url.encode("utf-8"), raw)
    return _ok(web)


def capability_profile(capability_id, changes):
    """SearXNG leases whatever host the instance URL names."""
    del changes
    from kernel.process.profiles import tool_with_network

    return tool_with_network(capability_id, ("*",))


def _get(url: str, headers: dict[str, str]):
    request = Request(url, headers={**headers, "User-Agent": "Linope-searxng/1.0"}, method="GET")
    opener = build_opener(_NoRedirect, HTTPSHandler(context=ssl.create_default_context()))
    try:
        with opener.open(request, timeout=TIMEOUT_SECONDS) as response:
            raw = response.read()
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        message = f"HTTP {exc.code}: {exc.reason}"
        if detail.strip():
            message = f"{message}: {detail.strip()}"
        return None, b"", _error(message)
    except URLError as exc:
        return None, b"", _error(str(exc.reason or exc))
    except TimeoutError:
        return None, b"", _error(f"search timed out after {int(TIMEOUT_SECONDS * 1000)}ms")
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError:
        return None, raw, _error("search backend returned invalid JSON")
    if not isinstance(parsed, dict):
        return None, raw, _error("search backend returned an unexpected payload")
    return parsed, raw, None


def _secret(name: str) -> str | None:
    from kernel.environment import current_room

    room = current_room()
    if room is not None:
        try:
            value = room.identity.resolve_secret(name)
        except RuntimeError:
            value = ""
        if str(value or "").strip():
            return str(value).strip()
    value = os.environ.get(name) or ""
    return value.strip() or None


def _limit(value: Any) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = 5
    return min(max(number, 1), 10)


def _charge(sent: bytes, received: bytes) -> None:
    from kernel.resource.account.recorded import record_network_current

    record_network_current(sent=len(sent), received=len(received))


def _ok(web: list[dict[str, Any]]) -> str:
    return json.dumps({"success": True, "data": {"web": web}}, ensure_ascii=False)


def _error(message: str, **details: Any) -> str:
    payload = {"success": False, "error": message}
    payload.update(details)
    return json.dumps(payload, ensure_ascii=False)
