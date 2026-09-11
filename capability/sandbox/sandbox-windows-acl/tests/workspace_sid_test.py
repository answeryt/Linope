# -*- coding: utf-8 -*-

from __future__ import annotations

import importlib.util
import re
from pathlib import Path


def _load():
    path = Path(__file__).resolve().parents[1] / "src" / "workspace_sid_plugin.py"
    spec = importlib.util.spec_from_file_location("sandbox_windows_acl_workspace_sid", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_workspace_sid_stable() -> None:
    sids = _load()
    first = sids.workspace_write_sid(r"C:\Users\agent\repo")
    assert first == sids.workspace_write_sid(r"C:\Users\agent\repo")
    assert re.fullmatch(r"S-1-4-\d+-\d+", first)


def test_workspace_sid_distinct_and_byte_sensitive() -> None:
    sids = _load()
    assert sids.workspace_write_sid(r"C:\Users\agent\repo-a") != sids.workspace_write_sid(
        r"C:\Users\agent\repo-b"
    )
    assert sids.workspace_write_sid(r"C:\Repo") != sids.workspace_write_sid(r"c:\repo")
    assert sids.workspace_write_sid("C:\\Repo\\") != sids.workspace_write_sid("C:\\Repo")


def test_temp_sid() -> None:
    sids = _load()
    temp = sids.temp_write_sid(r"C:\Users\agent\AppData\Local\Temp\dsh-abc123")
    assert temp == sids.temp_write_sid(r"C:\Users\agent\AppData\Local\Temp\dsh-abc123")
    assert re.fullmatch(r"S-1-4-\d+-\d+-1", temp)
    assert temp != sids.workspace_write_sid(r"C:\Users\agent\AppData\Local\Temp\dsh-abc123")
    assert sids.temp_write_sid(r"C:\Temp\dsh-a") != sids.temp_write_sid(r"C:\Temp\dsh-b")


if __name__ == "__main__":
    test_workspace_sid_stable()
    test_workspace_sid_distinct_and_byte_sensitive()
    test_temp_sid()
    print("workspace_sid_test ok")
