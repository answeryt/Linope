#!/usr/bin/env python3

import json
import os
from typing import Any


def env_var_enabled(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    return default if value is None else value.strip().lower() in {"1", "true", "yes", "on"}


def tool_error(message: str) -> str:
    return json.dumps({"success": False, "error": message}, ensure_ascii=False)


class _StandaloneDesktopUI:
    def emit(self, _event: str, _payload: dict) -> bool:
        return False


class _StandaloneRegistry:
    def register(self, **_kwargs: Any) -> None:
        return None


desktop_ui = _StandaloneDesktopUI()
registry = _StandaloneRegistry()

PANES = ("chat", "files", "terminal", "review", "sessions")


def focus_pane_tool(pane: str) -> str:
    """Ask the desktop GUI to reveal and focus ``pane``."""
    name = (pane or "").strip().lower()
    if name not in PANES:
        return tool_error(f"pane must be one of: {', '.join(PANES)}.")

    try:
        ok = desktop_ui.emit("pane.reveal", {"pane": name})
    except Exception as exc:
        return tool_error(f"Failed to focus the {name} pane: {exc}")
    if not ok:
        return tool_error("Pane focus is only available in the Hermes desktop app.")

    return json.dumps({"success": True, "pane": name}, ensure_ascii=False)


def check_focus_pane_requirements() -> bool:
    """Desktop GUI only — HERMES_DESKTOP is set on the gateway the app spawns."""
    return env_var_enabled("HERMES_DESKTOP")


FOCUS_PANE_SCHEMA = {
    "name": "focus_pane",
    "description": (
        "Reveal and focus a pane in the Hermes desktop app when the user asks to "
        "see it — e.g. \"show me the terminal\", \"open the file browser\", \"show "
        "the diff\". Panes: chat (the conversation), files (project file browser), "
        "terminal (embedded shell), review (git diff), sessions (the session list). "
        "To show a URL or file in the preview pane, use open_preview instead."
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


registry.register(
    name="focus_pane",
    toolset="terminal",
    schema=FOCUS_PANE_SCHEMA,
    handler=lambda args, **kw: focus_pane_tool(pane=args.get("pane", "")),
    check_fn=check_focus_pane_requirements,
    emoji="🪟",
)
