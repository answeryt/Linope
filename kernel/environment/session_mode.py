"""Read the session sandbox mode from capability/sandbox. No second fold."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any


_PLUGIN = (
    Path(__file__).resolve().parents[2]
    / "capability"
    / "sandbox"
    / "sandbox-policy"
    / "src"
    / "session_mode_plugin.py"
)
_CACHE: Any = None


def _plugin() -> Any:
    global _CACHE
    if _CACHE is None:
        spec = importlib.util.spec_from_file_location("linope_sandbox_session_mode", _PLUGIN)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"Cannot open the session sandbox mode: {_PLUGIN}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _CACHE = module
    return _CACHE


def effective_mode(events: Any) -> str | None:
    """The last sandbox/mode event, or None when the session never switched."""
    return _plugin().effective_sandbox_mode(events)


def remember_mode(folder: str | None, mode: str) -> None:
    """Append one sandbox/mode event. The event is the session mode."""
    import os

    from kernel.environment.sandbox_vocab import check_mode
    from kernel.trace.journal import Journal, journal_path

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
