# -*- coding: utf-8 -*-
"""Pin writable-root derivation: workspace-write allow-list, read-only empty."""

from __future__ import annotations

import importlib.util
import os
import tempfile
from pathlib import Path


def _load():
    path = Path(__file__).resolve().parents[1] / "src" / "roots_plugin.py"
    spec = importlib.util.spec_from_file_location("sandbox_roots", path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_canonical_path_resolves_existing() -> None:
    roots = _load()
    with tempfile.TemporaryDirectory(prefix="ol-roots-") as raw:
        assert roots.canonical_path(raw) == os.path.realpath(raw, strict=True)


def test_canonical_path_keeps_missing_spelling() -> None:
    roots = _load()
    missing = "/does/not/exist/anywhere-xyz"
    assert roots.canonical_path(missing) == missing


def test_read_only_grants_nothing() -> None:
    roots = _load()
    assert roots.writable_roots({"mode": "read-only", "workspace_root": os.getcwd()}) == []


def test_danger_full_access_grants_nothing() -> None:
    roots = _load()
    assert roots.writable_roots({"mode": "danger-full-access", "workspace_root": os.getcwd()}) == []


def test_workspace_write_grants_canonical_deduped_roots() -> None:
    roots = _load()
    with tempfile.TemporaryDirectory(prefix="ol-ws-") as raw:
        granted = roots.writable_roots({"mode": "workspace-write", "workspace_root": raw})
        assert os.path.realpath(raw, strict=True) in granted
        assert roots.canonical_path("/tmp") in granted
        assert os.path.realpath(tempfile.gettempdir(), strict=True) in granted
        assert len(set(granted)) == len(granted)


if __name__ == "__main__":
    test_canonical_path_resolves_existing()
    test_canonical_path_keeps_missing_spelling()
    test_read_only_grants_nothing()
    test_danger_full_access_grants_nothing()
    test_workspace_write_grants_canonical_deduped_roots()
    print("roots_test ok")
