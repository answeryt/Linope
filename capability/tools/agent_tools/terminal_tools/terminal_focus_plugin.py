# -*- coding: utf-8 -*-
"""Reveal and focus a desktop pane when the Host injects an emitter."""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from typing import Any


PLUGIN_NAME = "terminal_focus"
PLUGIN_VERSION = "1.0"

EmitFn = Callable[[str, dict[str, Any]], bool]

PANES = ("chat", "files", "terminal", "review", "sessions")


def _truthy(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def tool_error(message: str) -> str:
    return json.dumps({"success": False, "error": message}, ensure_ascii=False)


def focus_pane_tool(pane: str, emit: EmitFn | None = None) -> str:
    name = (pane or "").strip().lower()
    if name not in PANES:
        return tool_error(f"pane must be one of: {', '.join(PANES)}.")
    if emit is None:
        return tool_error("Pane focus is only available when a desktop emitter is injected.")
    try:
        ok = emit("pane.reveal", {"pane": name})
    except Exception as exc:
        return tool_error(f"Failed to focus the {name} pane: {exc}")
    if not ok:
        return tool_error("The desktop app did not accept the pane focus request.")
    return json.dumps({"success": True, "pane": name}, ensure_ascii=False)


def check_focus_pane_requirements() -> bool:
    return _truthy("DESKTOP_APP")


FOCUS_PANE_SCHEMA = {
    "name": "focus_pane",
    "description": (
        "Reveal and focus a pane in the desktop app: chat, files, "
        "terminal, review, or sessions. To show a URL or file in the "
        "preview pane, use open_preview instead."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "pane": {
                "type": "string",
                "enum": list(PANES),
                "description": "Which pane to reveal.",
            },
        },
        "required": ["pane"],
    },
}

def capability_profile(capability_id, changes):
    """Tell the process this tool needs a tool resource."""
    from kernel.process.declaration import ProcessDeclaration, ResourceClaim
    from kernel.resource.definition import ResourceKind

    return ProcessDeclaration(
        capability=capability_id,
        resources=(
            ResourceClaim(kind=ResourceKind.TOOL, identity={"id": capability_id}),
        ),
    )

