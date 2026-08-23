# -*- coding: utf-8 -*-

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load(name: str, filename: str, family: str):
    if family == "local":
        path = Path(__file__).resolve().parents[1] / "src" / filename
    else:
        path = Path(__file__).resolve().parents[2] / "sandbox" / "src" / filename
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sandbox(platform: str | None = None):
    profiles = _load("sandbox_profiles", "profiles_plugin.py", "local")
    roots = _load("sandbox_roots", "roots_plugin.py", "vocab")
    local = _load("sandbox_local", "sandbox_local_plugin.py", "local")
    return local, local.build_local_sandbox(
        bwrap_profile_args=profiles.bwrap_profile_args,
        landlock_profile_args=profiles.landlock_profile_args,
        seatbelt_profile_args=profiles.seatbelt_profile_args,
        writable_roots=roots.writable_roots,
        platform=platform or sys.platform,
    )


def test_profiles() -> None:
    profiles = _load("sandbox_profiles", "profiles_plugin.py", "local")
    policy = {"mode": "workspace-write", "workspace_root": "/ws"}
    bwrap = profiles.bwrap_profile_args(policy)
    assert "--bind" in bwrap and "/ws" in bwrap
    assert "--bind" not in profiles.bwrap_profile_args({"mode": "read-only", "workspace_root": "/ws"})
    landlock = profiles.landlock_profile_args(policy)
    assert "--rw" in landlock and "/ws" in landlock


def test_danger_full_access_skips_confine() -> None:
    _plugin, sandbox = _sandbox("win32")
    try:
        sandbox.confine(["cmd", "/c", "echo"], {"mode": "danger-full-access", "workspace_root": "C:\\ws"})
    except ValueError as exc:
        assert "danger-full-access" in str(exc)
    else:
        raise AssertionError("expected confine rejection")


def test_win32_confine_wraps_windows_runner() -> None:
    _plugin, sandbox = _sandbox("win32")
    result = sandbox.confine(
        ["cmd", "/c", "echo"],
        {"mode": "read-only", "workspace_root": "C:\\ws"},
    )
    assert result["enforcement"] == "partial"
    assert result["argv"][0] == sys.executable
    assert result["argv"][-3:] == ["--", "cmd", "/c"] or "cmd" in result["argv"]
    assert "--mode" in result["argv"]
    assert "read-only" in result["argv"]
    assert "windows-acl-run: " in result["runner_failure_rules"][0]["fatal_signatures"]


if __name__ == "__main__":
    test_profiles()
    test_danger_full_access_skips_confine()
    test_win32_confine_wraps_windows_runner()
    print("local_test ok")
