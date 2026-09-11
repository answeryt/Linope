# -*- coding: utf-8 -*-

from __future__ import annotations

import importlib.util
from pathlib import Path


def _load():
    path = Path(__file__).resolve().parents[1] / "src" / "runner_plugin.py"
    spec = importlib.util.spec_from_file_location("sandbox_windows_acl_runner", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_parse_args() -> None:
    runner = _load()
    parsed = runner.parse_args(
        ["--workspace", "C:\\ws", "--temp", "C:\\tmp", "--mode", "read-only", "--", "cmd", "/c", "echo"]
    )
    assert parsed["workspace"] == "C:\\ws"
    assert parsed["mode"] == "read-only"
    assert parsed["command"] == "cmd"
    assert parsed["args"] == ["/c", "echo"]


def test_parse_requires_mode() -> None:
    runner = _load()
    try:
        runner.parse_args(["--workspace", "C:\\ws", "--temp", "C:\\tmp", "--mode", "yolo", "--", "cmd"])
    except runner.RunnerFailure:
        pass
    else:
        raise AssertionError("expected unknown mode")


if __name__ == "__main__":
    test_parse_args()
    test_parse_requires_mode()
    print("runner_parse_test ok")
