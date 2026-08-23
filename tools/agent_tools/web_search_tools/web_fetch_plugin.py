# -*- coding: utf-8 -*-
"""Fetch one HTTP(S) URL and return decoded text."""

from __future__ import annotations

import json
import ssl
from typing import Any, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


PLUGIN_NAME = "web_fetch"
PLUGIN_VERSION = "1.0"

DEFAULT_MAX_CHARS = 200_000
TIMEOUT_SECONDS = 30

WEB_FETCH_SCHEMA: dict[str, Any] = {
    "name": "web_fetch",
    "description": "Fetch the content of a specific HTTP(S) URL and return it decoded to text.",
    "parameters": {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "The HTTP(S) URL to fetch.",
            },
        },
        "required": ["url"],
    },
}


def tool_schemas() -> list[dict[str, Any]]:
    return [WEB_FETCH_SCHEMA]


def dispatch(name: str, arguments: dict[str, Any], **kwargs: Any) -> str:
    if name != "web_fetch":
        return _error(f"unknown tool: {name}")
    return web_fetch(str(arguments.get("url") or ""), **kwargs)


def web_fetch(
    url: str,
    timeout_s: float = TIMEOUT_SECONDS,
    max_chars: int = DEFAULT_MAX_CHARS,
) -> str:
    """GET `url` and return decoded text, truncated at `max_chars`."""
    if not url.strip():
        return _error("url must be a non-empty string")
    if not url.startswith(("http://", "https://")):
        return _error("url must be an HTTP(S) URL")
    request = Request(
        url,
        headers={"User-Agent": "Open-Linux-web_fetch/1.0"},
        method="GET",
    )
    context = ssl.create_default_context()
    try:
        with urlopen(request, timeout=timeout_s, context=context) as response:
            raw = response.read()
            charset = response.headers.get_content_charset() or "utf-8"
            status = getattr(response, "status", 200)
            final_url = str(response.geturl())
    except HTTPError as exc:
        return _error(f"HTTP {exc.code}: {exc.reason}", status=exc.code)
    except URLError as exc:
        return _error(str(exc.reason or exc))
    except TimeoutError:
        return _error(f"fetch timed out after {int(timeout_s * 1000)}ms")
    text = raw.decode(charset, errors="replace")
    truncated = len(text) > max_chars
    if truncated:
        text = text[:max_chars]
    return json.dumps(
        {
            "success": True,
            "url": final_url,
            "status": status,
            "text": text,
            "truncated": truncated,
        },
        ensure_ascii=False,
    )


def _error(message: str, **details: Any) -> str:
    payload = {"success": False, "error": message}
    payload.update(details)
    return json.dumps(payload, ensure_ascii=False)
