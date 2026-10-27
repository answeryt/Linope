# -*- coding: utf-8 -*-
"""plugin-unit: load tokens by file, never through Host."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


def _load():
    path = Path(__file__).resolve().parents[1] / "tokens" / "tokens.py"
    spec = importlib.util.spec_from_file_location("tokens_leaf", path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TokensTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tokens = _load()

    def test_ascii_and_cjk_text_estimates(self) -> None:
        self.assertEqual(self.tokens.estimate_text_tokens_rough(""), 0)
        self.assertEqual(self.tokens.estimate_text_tokens_rough("abcd"), 1)
        self.assertEqual(self.tokens.estimate_text_tokens_rough("\uac00\uac01"), 2)

    def test_image_count_uses_fixed_cost(self) -> None:
        message = {
            "role": "user",
            "content": [
                {"type": "text", "text": "see"},
                {"type": "image_url", "image_url": {"url": "x"}},
            ],
        }
        self.assertEqual(
            self.tokens.estimate_image_tokens(message),
            self.tokens.DEFAULT_IMAGE_TOKEN_COST,
        )

    def test_messages_use_local_estimators_by_default(self) -> None:
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "hi"},
                    {"type": "image", "source": {}},
                ],
            }
        ]
        total = self.tokens.estimate_messages_tokens_rough(messages)
        text_only = self.tokens.estimate_message_tokens_rough(messages[0])
        self.assertGreater(total, text_only)
        self.assertEqual(total, text_only + self.tokens.DEFAULT_IMAGE_TOKEN_COST)

    def test_tool_schema_estimate(self) -> None:
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "read",
                    "description": "Read a file",
                    "parameters": {"type": "object", "properties": {}},
                },
            }
        ]
        self.assertGreater(self.tokens.estimate_tool_tokens_rough(tools), 0)


if __name__ == "__main__":
    unittest.main()
