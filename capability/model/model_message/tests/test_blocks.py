# -*- coding: utf-8 -*-
"""plugin-unit: load message blocks by file, never through Host."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


def _load():
    path = Path(__file__).resolve().parents[1] / "blocks.py"
    spec = importlib.util.spec_from_file_location("message_blocks_leaf", path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class MessageBlocksTest(unittest.TestCase):
    def setUp(self) -> None:
        self.blocks = _load()

    def test_text_and_thinking_blocks(self) -> None:
        text = self.blocks.TextBlock(text="hello")
        thinking = self.blocks.ThinkingBlock(thinking="reason")
        self.assertEqual(text.type, "text")
        self.assertEqual(thinking.type, "thinking")
        self.assertTrue(text.id)
        self.assertNotEqual(text.id, thinking.id)

    def test_tool_call_and_result_states(self) -> None:
        call = self.blocks.ToolCallBlock(id="1", name="read", input="{}")
        result = self.blocks.ToolResultBlock(id="1", name="read", output="ok")
        self.assertEqual(call.state, self.blocks.ToolCallState.PENDING)
        self.assertEqual(result.state, self.blocks.ToolResultState.RUNNING)


if __name__ == "__main__":
    unittest.main()
