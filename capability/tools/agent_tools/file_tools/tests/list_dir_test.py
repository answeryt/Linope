# -*- coding: utf-8 -*-
"""plugin-unit sample: list one directory level."""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


def _load():
    path = Path(__file__).resolve().parents[1] / "list_dir_plugin.py"
    spec = importlib.util.spec_from_file_location("list_dir_plugin_leaf", path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ListDirPluginTest(unittest.TestCase):
    def setUp(self) -> None:
        self.plugin = _load()

    def test_lists_one_level_with_file_and_dir_kinds(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "notes.txt").write_text("alpha\n", encoding="utf-8")
            (root / "more").mkdir()
            (root / "more" / "inside.txt").write_text("hidden from this level\n", encoding="utf-8")
            payload = json.loads(
                self.plugin.dispatch("list_dir", {"path": str(root)}, workspace=str(root))
            )

        self.assertTrue(payload["success"])
        names = {item["name"]: item["kind"] for item in payload["entries"]}
        self.assertEqual(names["notes.txt"], "file")
        self.assertEqual(names["more"], "dir")
        self.assertNotIn("inside.txt", names)

    def test_missing_directory_is_a_tool_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            missing = str(Path(directory) / "gone")
            payload = json.loads(
                self.plugin.dispatch("list_dir", {"path": missing}, workspace=directory)
            )
        self.assertFalse(payload["success"])
        self.assertIn("directory not found", payload["error"])


if __name__ == "__main__":
    unittest.main()
