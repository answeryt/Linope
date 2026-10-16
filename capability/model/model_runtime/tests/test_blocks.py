from __future__ import annotations

import unittest
from types import SimpleNamespace

from capability.model.model_runtime.assembler import BlockAssembler
from capability.model.model_runtime.blocks import turn_from_payload
from capability.model.model_runtime.usage import read_usage


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

    def test_parallel_tool_calls_keep_their_own_index(self) -> None:
        assembler = BlockAssembler()
        assembler.push({"type": "tool-call-delta", "index": 0, "id": "a", "name": "tools.read", "arguments": "{}"})
        assembler.push({"type": "tool-call-delta", "index": 1, "id": "b", "name": "tools.grep", "arguments": "{}"})
        calls = assembler.finish().tool_calls()
        self.assertEqual([call.id for call in calls], ["a", "b"])
        self.assertEqual([call.name for call in calls], ["tools.read", "tools.grep"])

    def test_a_tool_call_without_a_name_is_reported(self) -> None:
        assembler = BlockAssembler()
        assembler.push({"type": "tool-call-delta", "index": 0, "arguments": "{}"})
        turn = assembler.finish()
        self.assertEqual(turn.tool_calls(), ())
        self.assertIn("no name", turn.text())

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

    def test_usage_parts_merge_input_then_output(self) -> None:
        assembler = BlockAssembler()
        assembler.push({"type": "text-delta", "text": "你好"})
        assembler.push({"type": "usage", "usage": {"input": 4}})
        assembler.push({"type": "usage", "usage": {"output": 2}})
        turn = assembler.finish()
        self.assertEqual(turn.usage, {"input": 4, "output": 2})
        self.assertEqual(read_usage(SimpleNamespace(completion_tokens=2, prompt_tokens=4)), {"input": 4, "output": 2})
        self.assertEqual(read_usage({"candidatesTokenCount": 3}), {"output": 3})

    def test_payload_round_trip(self) -> None:
        assembler = BlockAssembler()
        assembler.push({"type": "text-delta", "text": "done"})
        turn = turn_from_payload(assembler.finish().to_payload())
        self.assertIsNotNone(turn)
        assert turn is not None
        self.assertEqual(turn.text(), "done")


if __name__ == "__main__":
    unittest.main()
