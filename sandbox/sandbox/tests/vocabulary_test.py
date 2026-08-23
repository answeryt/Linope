# -*- coding: utf-8 -*-
"""Pin the three modes and the fail-closed SANDBOX_UNAVAILABLE identity."""

from __future__ import annotations

import importlib.util
from pathlib import Path


def _load():
    path = Path(__file__).resolve().parents[1] / "src" / "sandbox_plugin.py"
    spec = importlib.util.spec_from_file_location("sandbox_provider", path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_three_modes() -> None:
    sandbox = _load()
    assert sandbox.SANDBOX_MODES == (
        "read-only",
        "workspace-write",
        "danger-full-access",
    )
    assert sandbox.CONFINED_MODES == ("read-only", "workspace-write")
    assert sandbox.requires_confine("read-only")
    assert sandbox.requires_confine("workspace-write")
    assert not sandbox.requires_confine("danger-full-access")


def test_unavailable_identity() -> None:
    sandbox = _load()
    error = sandbox.SandboxUnavailableError("read-only")
    assert error.name == "SandboxUnavailableError"
    assert error.code == sandbox.SANDBOX_UNAVAILABLE
    assert isinstance(error, Exception)


def test_unavailable_message() -> None:
    sandbox = _load()
    error = sandbox.SandboxUnavailableError("workspace-write")
    assert '"workspace-write"' in str(error)
    assert "danger-full-access" in str(error)
    assert "Runner failure" not in str(error)


def test_unavailable_runner_detail() -> None:
    sandbox = _load()
    error = sandbox.SandboxUnavailableError(
        "read-only",
        "landlock-run: landlock is not enforced by this kernel",
    )
    assert error.code == sandbox.SANDBOX_UNAVAILABLE
    assert "Runner failure: landlock-run: landlock is not enforced by this kernel" in str(error)


def test_confine_rejects_danger_full_access() -> None:
    sandbox = _load()
    try:
        sandbox.require_confined_mode("danger-full-access")
    except ValueError as exc:
        assert "danger-full-access" in str(exc)
    else:
        raise AssertionError("expected confine rejection")


if __name__ == "__main__":
    test_three_modes()
    test_unavailable_identity()
    test_unavailable_message()
    test_unavailable_runner_detail()
    test_confine_rejects_danger_full_access()
    print("vocabulary_test ok")
