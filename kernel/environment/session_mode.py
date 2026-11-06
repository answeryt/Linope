"""Read the session sandbox mode. The sandbox program owns the mode names."""

from __future__ import annotations

import os
from typing import Any

from kernel.environment.sandbox_vocab import check_mode
from kernel.trace.journal import Journal, journal_path


def effective_mode(events: Any) -> str | None:
    """The last sandbox/mode event, or None when the session never switched."""
    found: str | None = None
    seen = False
    for event in events or []:
        if not isinstance(event, dict) or str(event.get("type") or "") != "sandbox/mode":
            continue
        data = event.get("data") if isinstance(event.get("data"), dict) else {}
        mode = data.get("mode")
        seen = True
        found = None if mode is None else str(mode)
    if not seen or found is None:
        return None
    return check_mode(found)


def remember_mode(folder: str | None, mode: str) -> None:
    """Append one sandbox/mode event. The event is the session mode."""
    checked = check_mode(mode)
    event = {"type": "sandbox/mode", "data": {"mode": checked}}
    seen: set[str] = set()
    for place in _places(folder, os.environ.get("LINOPE_SESSION_ROOT") or None):
        path = journal_path(place)
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        Journal(path).append(event)


def _places(folder: str | None, env_root: str | None) -> tuple[str | None, ...]:
    if env_root:
        return (env_root,)
    if not folder:
        return (None,)
    return (folder, None)
