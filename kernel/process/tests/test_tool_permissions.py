"""Sandbox mode stays with the capability sandbox. The agent loop does not pick it."""

import importlib.util
import os
from pathlib import Path


def _plugin(relative: str, name: str):
    path = Path(__file__).resolve().parents[3] / relative
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _policy():
    plugin = _plugin("capability/sandbox/sandbox-policy/src/sandbox_policy_plugin.py", "sandbox_policy_perm")
    return plugin.SandboxPolicy(
        canonical_path=os.path.abspath,
        effective_mode=lambda events: None,
    )


def test_the_default_mode_is_read_only(tmp_path: Path) -> None:
    resolved = _policy().resolve({"session": None})
    assert resolved["mode"] == "read-only"
    roots = _plugin("capability/sandbox/sandbox/src/roots_plugin.py", "sandbox_roots_perm")
    assert roots.writable_roots({"mode": "read-only", "workspace_root": str(tmp_path)}) == []


def test_an_approved_mode_is_the_mode_that_was_named() -> None:
    assert _policy().resolve({"mode": "workspace-write"})["mode"] == "workspace-write"


def test_the_agent_loop_does_not_choose_a_sandbox_mode() -> None:
    root = Path(__file__).resolve().parents[3]
    source = (root / "capability" / "agent_loop" / "pi" / "main.mjs").read_text(encoding="utf-8")
    loop = (root / "capability" / "agent_loop" / "pi" / "loop.mjs").read_text(encoding="utf-8")
    for text in (source, loop):
        assert "workspace-write" not in text
        assert "danger-full-access" not in text
        assert "confine(" not in text
