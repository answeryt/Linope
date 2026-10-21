# -*- coding: utf-8 -*-
"""Search the web through the installed ddgs package."""

from __future__ import annotations

import json
from typing import Any


PLUGIN_NAME = "ddgs"
PLUGIN_VERSION = "1.0"

DDGS_SCHEMA: dict[str, Any] = {
    "name": "ddgs",
    "description": "Search the web with DuckDuckGo via the ddgs package. Returns titles, URLs, and descriptions.",
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


def tool_schemas() -> list[dict[str, Any]]:
    return [DDGS_SCHEMA]


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
    return ddgs_search(
        str(arguments.get("query") or ""),
        limit=arguments.get("limit", 5),
    )


def ddgs_search(query: str, limit: int = 5) -> str:
    """Run a text search with the ddgs package."""
    query = query.strip()
    if not query:
        return _error("query must be a non-empty string")
    limit = _limit(limit)
    try:
        from ddgs import DDGS
    except ImportError:
        return _error("ddgs package is not installed")
    try:
        rows = list(DDGS().text(query, max_results=limit) or [])
    except Exception as exc:
        return _error(str(exc))
    web = []
    for index, item in enumerate(rows, start=1):
        if not isinstance(item, dict):
            continue
        url = str(item.get("href") or item.get("url") or "")
        title = str(item.get("title") or "")
        if not url and not title:
            continue
        web.append(
            {
                "title": title,
                "url": url,
                "description": str(item.get("body") or item.get("description") or ""),
                "position": index,
            }
        )
    return _ok(web)


def capability_profile(capability_id, changes):
    """DuckDuckGo search leases a tool and the ledger channel. It does not receive a workspace."""
    del changes
    from kernel.process.profiles import tool_only

    return tool_only(capability_id)


def _limit(value: Any) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = 5
    return min(max(number, 1), 10)


def _ok(web: list[dict[str, Any]]) -> str:
    return json.dumps({"success": True, "data": {"web": web}}, ensure_ascii=False)


def _error(message: str, **details: Any) -> str:
    payload = {"success": False, "error": message}
    payload.update(details)
    return json.dumps(payload, ensure_ascii=False)
