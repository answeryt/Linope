# -*- coding: utf-8 -*-
"""Open a URL or file in the desktop preview pane when the Host injects an emitter."""

from __future__ import annotations

import json
import os
import re
from collections.abc import Callable
from typing import Any


PLUGIN_NAME = "terminal_preview"
PLUGIN_VERSION = "1.0"

EmitFn = Callable[[str, dict[str, Any]], bool]


def _truthy(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def tool_error(message: str) -> str:
    return json.dumps({"success": False, "error": message}, ensure_ascii=False)


def _normalize_target(raw: str) -> str:
    value = raw.strip().strip("`").strip()
    if not value or "://" in value or value.startswith(("/", "./", "../", "~", "file:")):
        return value
    if re.match(r"^(localhost|127\.0\.0\.1|0\.0\.0\.0|\[::1\])(:\d+)?(/|$)", value, re.I):
        return "http://" + value
    if re.match(r"^[\w.-]+\.[a-z]{2,}(:\d+)?(/.*)?$", value, re.I):
        return "https://" + value
    return value


def open_preview_tool(
    url: str,
    label: str = "",
    emit: EmitFn | None = None,
) -> str:
    target = _normalize_target(url or "")
    if not target:
        return tool_error(
            "url is required — a web URL, a localhost dev server, or a file path."
        )
    caption = (label or "").strip()
    if emit is None:
        return tool_error("The preview pane is only available when a desktop emitter is injected.")
    try:
        ok = emit("preview.open", {"url": target, "label": caption})
    except Exception as exc:
        return tool_error(f"Failed to open the preview pane: {exc}")
    if not ok:
        return tool_error("The desktop app did not accept the preview request.")
    return json.dumps({"success": True, "url": target, "label": caption}, ensure_ascii=False)


def check_open_preview_requirements() -> bool:
    return _truthy("DESKTOP_APP")


OPEN_PREVIEW_SCHEMA = {
    "name": "open_preview",
    "description": (
        "Open a web URL, localhost dev server, or file path in the preview "
        "pane beside the chat."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "Web URL, bare domain, localhost URL, or file path.",
            },
            "label": {
                "type": "string",
                "description": "Optional tab label; defaults to the target name.",
            },
        },
        "required": ["url"],
    },
}
