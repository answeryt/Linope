# -*- coding: utf-8 -*-
"""Pin sandbox/mode fold, write path, and closed mode vocabulary."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any


def _load():
    path = Path(__file__).resolve().parents[1] / "src" / "session_mode_plugin.py"
    spec = importlib.util.spec_from_file_location("sandbox_session_mode", path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _Session:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    def append(self, event_type: str, data: dict[str, Any]) -> None:
        self.events.append({"type": event_type, "data": data})


def test_modes() -> None:
    mode = _load()
    assert mode.SANDBOX_MODES == ("read-only", "workspace-write", "danger-full-access")


def test_fold_last_switch() -> None:
    mode = _load()
    session = _Session()
    assert mode.effective_sandbox_mode(session.events) is None
    mode.set_sandbox_mode(session, "workspace-write")
    mode.set_sandbox_mode(session, "read-only")
    assert mode.effective_sandbox_mode(session.events) == "read-only"


def test_set_appends_one_event() -> None:
    mode = _load()
    session = _Session()
    mode.set_sandbox_mode(session, "danger-full-access")
    events = [item for item in session.events if item["type"] == "sandbox/mode"]
    assert len(events) == 1
    assert events[0]["data"] == {"mode": "danger-full-access"}


def test_validate_mode_event() -> None:
    mode = _load()
    mode.validate_mode_event({"type": "sandbox/mode", "data": {"mode": "read-only"}})
    mode.validate_mode_event({"type": "turn/start", "data": {}})
    try:
        mode.validate_mode_event({"type": "sandbox/mode", "data": {"mode": "host-root"}})
    except ValueError as exc:
        assert "unknown mode" in str(exc)
    else:
        raise AssertionError("expected unknown mode error")


if __name__ == "__main__":
    test_modes()
    test_fold_last_switch()
    test_set_appends_one_event()
    test_validate_mode_event()
    print("session_mode_test ok")
