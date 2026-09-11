# -*- coding: utf-8 -*-
"""Pin policy resolve: approved mode > session override > default read-only."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from typing import Any


def _load(name: str, filename: str, family: str):
    if family == "policy":
        path = Path(__file__).resolve().parents[1] / "src" / filename
    else:
        path = Path(__file__).resolve().parents[2] / "sandbox" / "src" / filename
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _Session:
    def __init__(self, session_id: str, cwd: str | None = None) -> None:
        self.id = session_id
        self.header = {"cwd": cwd} if cwd is not None else {}
        self.events: list[dict[str, Any]] = []

    def append(self, event_type: str, data: dict[str, Any]) -> None:
        self.events.append({"type": event_type, "data": data})


def _policy(**config: Any):
    roots = _load("sandbox_roots", "roots_plugin.py", "vocab")
    modes = _load("sandbox_session_mode", "session_mode_plugin.py", "policy")
    plugin = _load("sandbox_policy", "sandbox_policy_plugin.py", "policy")
    return plugin, modes, plugin.SandboxPolicy(
        canonical_path=roots.canonical_path,
        effective_mode=modes.effective_sandbox_mode,
        **config,
    )


def test_default_read_only_under_cwd() -> None:
    _plugin, _modes, service = _policy()
    assert service.default_mode == "read-only"
    assert service.workspace_root == os.path.abspath(os.getcwd())


def test_configured_mode_and_absolute_root() -> None:
    _plugin, _modes, service = _policy(
        mode="workspace-write",
        workspace_root=os.path.join("ws", "..", "ws", "sub"),
    )
    assert service.default_mode == "workspace-write"
    assert service.workspace_root == os.path.abspath(os.path.join("ws", "..", "ws", "sub"))


def test_agentless_resolve() -> None:
    _plugin, _modes, service = _policy(mode="workspace-write", workspace_root="fallback")
    assert service.resolve() == {
        "mode": "workspace-write",
        "workspace_root": os.path.abspath("fallback"),
    }


def test_per_session_mode_and_cwd() -> None:
    plugin, modes, service = _policy(mode="workspace-write", workspace_root="fallback")
    first = _Session("sess-first", os.path.join("projects", "first"))
    second = _Session("sess-second", os.path.join("projects", "second"))
    modes.set_sandbox_mode(second, "read-only")
    assert service.resolve({"session": first}) == {
        "mode": "workspace-write",
        "workspace_root": os.path.abspath(os.path.join("projects", "first")),
        "session_id": "sess-first",
    }
    assert service.resolve({"session": second}) == {
        "mode": "read-only",
        "workspace_root": os.path.abspath(os.path.join("projects", "second")),
        "session_id": "sess-second",
    }
    assert service.override_of(first) is None
    assert service.override_of(second) == "read-only"
    assert service.resolve()["mode"] == "workspace-write"


def test_approved_mode_outranks_session() -> None:
    _plugin, modes, service = _policy(workspace_root="fallback")
    active = _Session("sess-approved", os.path.join("projects", "approved"))
    modes.set_sandbox_mode(active, "read-only")
    resolved = service.resolve({"session": active, "mode": "danger-full-access"})
    assert resolved["mode"] == "danger-full-access"
    assert resolved["workspace_root"] == os.path.abspath(os.path.join("projects", "approved"))
    assert resolved["session_id"] == "sess-approved"


def test_session_without_cwd_uses_fallback() -> None:
    _plugin, _modes, service = _policy(workspace_root="fallback")
    resolved = service.resolve({"session": _Session("sess-no-cwd")})
    assert resolved["workspace_root"] == os.path.abspath("fallback")


def test_rejects_unknown_default_mode() -> None:
    plugin, modes, _service = _policy()
    try:
        plugin.SandboxPolicy(
            canonical_path=lambda path: path,
            effective_mode=modes.effective_sandbox_mode,
            mode="yolo",
        )
    except ValueError as exc:
        assert "unknown sandbox mode" in str(exc)
    else:
        raise AssertionError("expected unknown mode error")


def test_render_three_modes() -> None:
    plugin, _modes, service = _policy(mode="read-only", workspace_root="fallback")
    workspace = os.path.abspath(os.path.join("projects", "current"))
    session = _Session("sess-render", os.path.join("projects", "current"))
    assert "read-only" in service.render({"session": session})
    write = plugin.render_policy_context(
        {"mode": "workspace-write", "workspace_root": workspace}
    )
    assert "workspace-write" in write
    assert repr(workspace) in write
    assert "danger-full-access" in plugin.render_policy_context(
        {"mode": "danger-full-access", "workspace_root": workspace}
    )


def test_render_without_agent_is_empty() -> None:
    _plugin, _modes, service = _policy()
    assert service.render() == ""


if __name__ == "__main__":
    test_default_read_only_under_cwd()
    test_configured_mode_and_absolute_root()
    test_agentless_resolve()
    test_per_session_mode_and_cwd()
    test_approved_mode_outranks_session()
    test_session_without_cwd_uses_fallback()
    test_rejects_unknown_default_mode()
    test_render_three_modes()
    test_render_without_agent_is_empty()
    print("policy_test ok")
