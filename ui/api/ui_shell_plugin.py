# -*- coding: utf-8 -*-
"""Shell JSON for the browser. Lists stay empty until a later store exists."""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from typing import Any


PLUGIN_NAME = "ui_shell"
PLUGIN_VERSION = "1.0"

Handler = Callable[[dict[str, str]], dict[str, Any]]


def empty_shell() -> dict[str, Any]:
    """No placeholder workspaces, sessions, messages, or model name."""
    return {
        "workspaces": [],
        "sessions": [],
        "messages": [],
        "selectedWorkspaceId": None,
        "selectedSessionId": None,
        "model": None,
        "cwd": os.getcwd(),
    }


def mount_shell(*, register: Callable[[str, str, Handler], None]) -> None:
    def handle(request: dict[str, str]) -> dict[str, Any]:
        method = str(request.get("method") or "GET").upper()
        if method not in ("GET", "HEAD"):
            return {"status": 405, "headers": {}, "body": b""}
        body = json.dumps(empty_shell(), separators=(",", ":")).encode("utf-8")
        return {
            "status": 200,
            "headers": {"content-type": "application/json; charset=utf-8"},
            "body": body,
        }

    register("exact", "/api/shell", handle)
