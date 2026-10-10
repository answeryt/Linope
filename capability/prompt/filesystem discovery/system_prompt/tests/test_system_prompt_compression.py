# -*- coding: utf-8 -*-
"""plugin-unit: load system_prompt_compression by file, never through Host."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


def _load():
    path = Path(__file__).resolve().parents[1] / "system_prompt_compression.py"
    spec = importlib.util.spec_from_file_location(
        "system_prompt_compression_leaf",
        path,
    )
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


PARAMETERS = {
    "enabled": True,
    "max_chars": 120,
    "chars_per_token": 4,
    "context_window_fraction": 0.5,
    "max_dynamic_chars": 200,
    "head_ratio": 1,
    "tail_ratio": 1,
}


class SystemPromptCompressionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.leaf = _load()

    def test_short_prompt_is_unchanged(self) -> None:
        text = "short"
        self.assertEqual(
            self.leaf.compress_system_prompt(text, PARAMETERS),
            text,
        )

    def test_long_prompt_keeps_head_and_tail(self) -> None:
        text = "A" * 80 + "MIDDLE" + "Z" * 80
        result = self.leaf.compress_system_prompt(text, PARAMETERS)
        self.assertTrue(result.startswith("A"))
        self.assertTrue(result.endswith("Z"))
        self.assertIn("truncated", result)
        self.assertNotIn("MIDDLE", result)

    def test_disabled_override_skips_truncation(self) -> None:
        text = "A" * 80
        result = self.leaf.compress_system_prompt(
            text,
            PARAMETERS,
            {"compress_system_prompt": False},
        )
        self.assertEqual(result, text)


if __name__ == "__main__":
    unittest.main()
