"""Tests for output_token_recovery.py, including a live lip model call."""

from __future__ import annotations

import importlib.util
import unittest

from plugins.model.model_API.model_paramaters.fallback_handlers.output_token_recovery import (
    is_output_cap_error,
    parse_available_output_tokens_from_error,
)
from plugins.model.model_API.model_paramaters.fallback_handlers.test.live_model import (
    API_KEY,
    ask_live_model,
)


class OutputTokenRecoveryTest(unittest.IsolatedAsyncioTestCase):
    def test_parses_supported_output_limit_errors(self) -> None:
        cases = (
            ("range of max_tokens should be [1, 4096]", 4_096),
            ("max_tokens exceeds available_tokens: 2048", 2_048),
            ("max_tokens exceeds available tokens 1024", 1_024),
            (
                "maximum context length is 10000 "
                "(6000 of text input, 1000 of tool input, 4000 in the output)",
                3_000,
            ),
        )
        for message, expected in cases:
            with self.subTest(message=message):
                self.assertEqual(
                    parse_available_output_tokens_from_error(message),
                    expected,
                )

    def test_identifies_output_cap_without_input_overflow(self) -> None:
        self.assertTrue(
            is_output_cap_error("max_tokens should be less than or equal to 4096")
        )
        self.assertFalse(
            is_output_cap_error(
                "max_tokens is invalid because the prompt is too long"
            )
        )
        self.assertFalse(is_output_cap_error("unrelated provider failure"))

    def test_returns_none_for_non_output_errors(self) -> None:
        self.assertIsNone(
            parse_available_output_tokens_from_error("prompt is too long")
        )

    @unittest.skipUnless(API_KEY, "OPENAI_API_KEY is not set")
    async def test_parses_output_error_text_returned_by_live_model(self) -> None:
        if importlib.util.find_spec("openai") is None:
            self.skipTest("openai package is not installed")
        text = await ask_live_model(
            "Reply with exactly this text and nothing else: "
            "range of max_tokens should be [1, 4096]"
        )
        self.assertTrue(is_output_cap_error(text), msg=text)
        self.assertEqual(
            parse_available_output_tokens_from_error(text),
            4_096,
            msg=text,
        )


if __name__ == "__main__":
    unittest.main()
