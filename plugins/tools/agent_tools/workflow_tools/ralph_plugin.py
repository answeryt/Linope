# -*- coding: utf-8 -*-
"""Foreground Ralph loop: one fresh child per round toward an immutable objective."""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from typing import Any, Optional


PLUGIN_NAME = "ralph"
PLUGIN_VERSION = "1.0"

RunFn = Callable[..., dict[str, Any]]
DEFAULT_MAX_ROUNDS = int(os.getenv("RALPH_MAX_ROUNDS", "64"))

RALPH_SCHEMA: dict[str, Any] = {
    "name": "ralph",
    "description": (
        "Run a foreground fresh-agent Ralph loop toward one immutable objective. "
        "Use only when the direct human explicitly asks for Ralph or fresh-agent "
        "iteration. Each round opens a new child with no parent conversation. "
        "The call returns when a worker reports completion or a concrete blocker, "
        "or at the round limit."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "objective": {
                "type": "string",
                "description": "The immutable completion objective for every fresh Ralph round.",
            },
            "maxRounds": {
                "type": "number",
                "description": "Optional positive safe-integer round cap, bounded by the deployment ceiling.",
            },
        },
        "required": ["objective"],
    },
}


def tool_schemas() -> list[dict[str, Any]]:
    return [RALPH_SCHEMA]


def dispatch(name: str, arguments: dict[str, Any], **kwargs: Any) -> str:
    if name != "ralph":
        return _error(f"unknown tool: {name}")
    return ralph(str(arguments.get("objective") or ""), arguments.get("maxRounds"), **kwargs)


def ralph(
    objective: str,
    max_rounds: Optional[float] = None,
    run: Optional[RunFn] = None,
) -> str:
    """Start a Ralph loop through the Host-injected runner."""
    if not objective.strip():
        return _error("objective must be a non-empty string")
    cap = DEFAULT_MAX_ROUNDS if max_rounds is None else int(max_rounds)
    if cap < 1:
        return _error("maxRounds must be a positive safe integer")
    if cap > DEFAULT_MAX_ROUNDS:
        cap = DEFAULT_MAX_ROUNDS
    if run is None:
        return _error(
            "No Ralph runner is attached. Host must inject a `run` callback "
            "that starts one fresh child per round."
        )
    result = run(objective=objective.strip(), max_rounds=cap)
    return json.dumps({"success": True, **result}, ensure_ascii=False)


def _error(message: str, **details: Any) -> str:
    payload = {"success": False, "error": message}
    payload.update(details)
    return json.dumps(payload, ensure_ascii=False)
