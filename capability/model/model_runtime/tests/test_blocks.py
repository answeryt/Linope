from __future__ import annotations

import unittest

from capability.model.model_runtime.assembler import BlockAssembler
from capability.model.model_runtime.blocks import turn_from_payload


class ModelBlocksTest(unittest.TestCase):
    def test_mixed_text_and_tool_call_are_separate(self) -> None:
        assembler = BlockAssembler()
        assembler.push({"type": "text-delta", "text": "我先查看目录。"})
        assembler.push(
            {
                "type": "tool-call-delta",
                "index": 0,
                "name": "tools.glob",
                "arguments": '{"pattern":"**/*"}',
            }
        )
        turn = assembler.finish()
        self.assertEqual(turn.text(), "我先查看目录。")
        self.assertEqual(len(turn.tool_calls()), 1)
        self.assertEqual(turn.tool_calls()[0].name, "tools.glob")

    def test_truncated_tool_call_is_not_executable(self) -> None:
        assembler = BlockAssembler()
        assembler.push(
            {
                "type": "tool-call-delta",
                "index": 0,
                "name": "tools.glob",
                "arguments": '{"pattern":"**/*"',
            }
        )
        assembler.push({"type": "finish", "reason": "length"})
        self.assertEqual(assembler.finish().tool_calls(), ())

    def test_payload_round_trip(self) -> None:
        assembler = BlockAssembler()
        assembler.push({"type": "text-delta", "text": "done"})
        turn = turn_from_payload(assembler.finish().to_payload())
        self.assertIsNotNone(turn)
        assert turn is not None
        self.assertEqual(turn.text(), "done")


if __name__ == "__main__":
    unittest.main()
