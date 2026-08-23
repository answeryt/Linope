# -*- coding: utf-8 -*-

from __future__ import annotations

import importlib.util
import os
import tempfile
from pathlib import Path


def _load():
    path = Path(__file__).resolve().parents[1] / "src" / "path_boundary_plugin.py"
    spec = importlib.util.spec_from_file_location("sandbox_windows_acl_path_boundary", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_rejects_temp_inside_workspace() -> None:
    boundary = _load()
    with tempfile.TemporaryDirectory(prefix="ol-acl-boundary-") as workspace:
        nested = os.path.join(workspace, "temp")
        os.mkdir(nested)
        try:
            boundary.assert_temp_root_outside_workspace(workspace, workspace)
        except ValueError as exc:
            assert "outside the workspace" in str(exc)
        else:
            raise AssertionError("expected equal-root rejection")
        try:
            boundary.assert_temp_root_outside_workspace(workspace, nested)
        except ValueError as exc:
            assert "outside the workspace" in str(exc)
        else:
            raise AssertionError("expected nested-root rejection")


def test_accepts_temp_parent_above_workspace() -> None:
    boundary = _load()
    with tempfile.TemporaryDirectory(prefix="ol-acl-boundary-") as temp_root:
        workspace = os.path.join(temp_root, "workspace")
        os.mkdir(workspace)
        boundary.assert_temp_root_outside_workspace(workspace, temp_root)


def test_private_temp_disjoint() -> None:
    boundary = _load()
    with tempfile.TemporaryDirectory(prefix="ol-acl-boundary-") as root:
        workspace = os.path.join(root, "workspace")
        nested = os.path.join(workspace, "temp")
        sibling = os.path.join(root, "sibling-temp")
        os.mkdir(workspace)
        os.mkdir(nested)
        os.mkdir(sibling)
        try:
            boundary.assert_private_temp_disjoint([workspace], nested)
        except ValueError as exc:
            assert "disjoint" in str(exc)
        else:
            raise AssertionError("expected nested temp rejection")
        boundary.assert_private_temp_disjoint([workspace], sibling)


if __name__ == "__main__":
    test_rejects_temp_inside_workspace()
    test_accepts_temp_parent_above_workspace()
    test_private_temp_disjoint()
    print("path_boundary_test ok")
