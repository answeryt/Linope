# -*- coding: utf-8 -*-

from __future__ import annotations

import importlib.util
from pathlib import Path


def _load():
    path = Path(__file__).resolve().parents[1] / "src" / "errors_plugin.py"
    spec = importlib.util.spec_from_file_location("sandbox_windows_acl_errors", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_win32_error() -> None:
    errors = _load()
    error = errors.Win32Error("CreateRestrictedToken", 1337, "bad SID")
    assert error.api == "CreateRestrictedToken"
    assert error.win32_code == 1337
    assert "1337" in str(error)
    assert "bad SID" in str(error)
    assert error.name == "Win32Error"


if __name__ == "__main__":
    test_win32_error()
    print("errors_test ok")
