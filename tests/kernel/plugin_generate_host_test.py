# -*- coding: utf-8 -*-

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path
from types import ModuleType


ROOT = Path(__file__).resolve().parents[2]
HOST_PATH = (
    ROOT
    / "capability"
    / "tools"
    / "external_tools"
    / "ci_tools"
    / "generate"
    / "plugin"
    / "plugin_generate.py"
)


def load(path: Path, module_name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


host = load(HOST_PATH, "plugin_generate_host_test_module")


class PluginGenerateHostTest(unittest.TestCase):
    def test_find_repo_root_without_legacy_composition(self) -> None:
        root = host.find_repo_root(HOST_PATH.parent)
        self.assertEqual(root, ROOT)
        self.assertTrue((root / "kernel" / "compose" / "capability").is_dir())
        self.assertTrue((root / "capability").is_dir())

    def test_skip_nested_sdk_checkouts(self) -> None:
        self.assertTrue(host._skip_dir_name("temporal-sdk-python"))
        self.assertTrue(host._skip_dir_name("restate-sdk-python"))
        self.assertTrue(host._skip_dir_name("tests"))


if __name__ == "__main__":
    unittest.main()
