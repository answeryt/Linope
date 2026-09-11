# -*- coding: utf-8 -*-
"""plugin-unit sample: load the read leaf by file, never through Host."""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


def _load():
    path = Path(__file__).resolve().parents[1] / "read_plugin.py"
    spec = importlib.util.spec_from_file_location("read_plugin_leaf", path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ReadPluginTest(unittest.TestCase):
    def setUp(self) -> None:
        self.read = _load()

    def test_leaf_identity_and_tool_contract(self) -> None:
        self.assertEqual(self.read.PLUGIN_NAME, "read")
        self.assertEqual(self.read.PLUGIN_VERSION, "1.0")
        schemas = self.read.tool_schemas()
        self.assertEqual(len(schemas), 1)
        self.assertEqual(schemas[0]["name"], "read")
        self.assertIn("file_path", schemas[0]["parameters"]["required"])

    def test_dispatch_rejects_unknown_tool(self) -> None:
        payload = json.loads(self.read.dispatch("write", {"file_path": "x"}))
        self.assertFalse(payload["success"])
        self.assertIn("unknown tool", payload["error"])

    def test_reads_numbered_window_inside_injected_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            (workspace / "notes.txt").write_text(
                "alpha\nbeta\ngamma\n",
                encoding="utf-8",
            )
            payload = json.loads(
                self.read.dispatch(
                    "read",
                    {"file_path": "notes.txt", "offset": 2, "limit": 1},
                    workspace=str(workspace),
                )
            )

        self.assertTrue(payload["success"])
        self.assertEqual(payload["lineCount"], 3)
        self.assertEqual(payload["returned"], 1)
        self.assertEqual(payload["content"], "     2|beta")

    def test_missing_file_is_a_tool_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            payload = json.loads(
                self.read.dispatch(
                    "read",
                    {"file_path": "missing.txt"},
                    workspace=directory,
                )
            )
        self.assertFalse(payload["success"])
        self.assertIn("file not found", payload["error"])


if __name__ == "__main__":
    unittest.main()
