# -*- coding: utf-8 -*-
"""plugin-unit: load system_prompt_builder by file, never through Host."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


def _load():
    path = Path(__file__).resolve().parents[1] / "system_prompt_builder.py"
    spec = importlib.util.spec_from_file_location("system_prompt_builder_leaf", path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class SystemPromptBuilderTest(unittest.TestCase):
    def setUp(self) -> None:
        self.builder = _load()

    def test_missing_plugin_returns_empty(self) -> None:
        self.assertEqual(self.builder.build_system_prompt(), "")

    def test_injected_plugin_fragments_are_joined(self) -> None:
        plugin = SimpleNamespace(
            enabled=lambda context=None: True,
            render=lambda context=None: (" first ", "second"),
        )
        self.assertEqual(
            self.builder.build_system_prompt(plugin=plugin),
            "first\n\nsecond",
        )

    def test_disabled_plugin_returns_empty(self) -> None:
        plugin = SimpleNamespace(
            enabled=lambda context=None: False,
            render=lambda context=None: ("kept",),
        )
        self.assertEqual(self.builder.build_system_prompt(plugin=plugin), "")

    def test_empty_separator_raises(self) -> None:
        plugin = SimpleNamespace(
            enabled=lambda context=None: True,
            render=lambda context=None: ("a",),
        )
        with self.assertRaises(ValueError):
            self.builder.build_system_prompt(separator="", plugin=plugin)


if __name__ == "__main__":
    unittest.main()
