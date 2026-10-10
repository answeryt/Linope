# -*- coding: utf-8 -*-
"""plugin-unit: load system_prompt_load by file, never through Host."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


def _load():
    path = Path(__file__).resolve().parents[1] / "system_prompt_load.py"
    spec = importlib.util.spec_from_file_location("system_prompt_load_leaf", path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class SystemPromptLoadTest(unittest.TestCase):
    def test_default_directory_is_prompt_card_system(self) -> None:
        leaf = _load()
        directory = leaf.get_system_prompt_directory()
        self.assertEqual(directory.name, "system")
        self.assertEqual(directory.parent.name, "prompt_card")
        self.assertTrue(directory.is_dir())

    def test_loads_non_empty_markdown(self) -> None:
        leaf = _load()
        prompts = leaf.load_system_prompt_files(leaf.get_system_prompt_directory())
        self.assertTrue(prompts)
        self.assertTrue(any("Role" in item for item in prompts))


if __name__ == "__main__":
    unittest.main()
