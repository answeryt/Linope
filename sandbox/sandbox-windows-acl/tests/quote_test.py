# -*- coding: utf-8 -*-

from __future__ import annotations

import importlib.util
from pathlib import Path


def _load():
    path = Path(__file__).resolve().parents[1] / "src" / "spawn_plugin.py"
    spec = importlib.util.spec_from_file_location("sandbox_windows_acl_spawn", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CASES = [
    ("", '""'),
    ("a", "a"),
    ("a b", '"a b"'),
    ('a"b', '"a\\"b"'),
    ("a\\b", "a\\b"),
    ("a b\\", '"a b\\\\"'),
    ("a b\\\\", '"a b\\\\\\\\"'),
    ("a b\\\\\\", '"a b\\\\\\\\\\\\"'),
    ('a\\\\"b', '"a\\\\\\\\\\"b"'),
]


def test_quote_arg() -> None:
    spawn = _load()
    for raw, quoted in CASES:
        assert spawn.quote_arg(raw) == quoted, raw


def test_build_command_line() -> None:
    spawn = _load()
    assert spawn.build_command_line("prog.exe", ["a b"]).startswith("prog.exe")


if __name__ == "__main__":
    test_quote_arg()
    test_build_command_line()
    print("quote_test ok")
