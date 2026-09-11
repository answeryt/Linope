"""Tests for context_error_recovery.py, including a live lip model call."""

from __future__ import annotations

import importlib.util
import unittest

from plugins.model.model_API.model_paramaters.fallback_handlers.context_error_recovery import (
    parse_context_limit_from_error,
    resolve_lower_context_limit_from_error,
)
from plugins.model.model_API.model_paramaters.fallback_handlers.test.live_model import (
    API_KEY,
    ask_live_model,
)


class ContextErrorRecoveryTest(unittest.IsolatedAsyncioTestCase):
    def test_parses_supported_provider_error_formats(self) -> None:
        cases = (
            ("max_model_len is 65536", 65_536),
            ("Maximum model length is 131072", 131_072),
            ("context window: 262144", 262_144),
            ("Request exceeds 128000 token context", 128_000),
        )
        for message, expected in cases:
            with self.subTest(message=message):
                self.assertEqual(
                    parse_context_limit_from_error(message),
                    expected,
                )

    def test_rejects_missing_or_unreasonable_limits(self) -> None:
        self.assertIsNone(parse_context_limit_from_error("request failed"))
        self.assertIsNone(parse_context_limit_from_error("context window: 512"))
        self.assertIsNone(
            parse_context_limit_from_error("context window: 10000001")
        )

    def test_only_resolves_a_lower_limit(self) -> None:
        error = "maximum context length is 131072"
        self.assertEqual(
            resolve_lower_context_limit_from_error(error, 256_000),
            131_072,
        )
        self.assertIsNone(
            resolve_lower_context_limit_from_error(error, 128_000)
        )

    @unittest.skipUnless(API_KEY, "OPENAI_API_KEY is not set")
    async def test_parses_error_text_returned_by_live_model(self) -> None:
        if importlib.util.find_spec("openai") is None:
            self.skipTest("openai package is not installed")
        text = await ask_live_model(
            "Reply with exactly this text and nothing else: "
            "maximum context length is 131072"
        )
        self.assertEqual(parse_context_limit_from_error(text), 131_072, msg=text)
        self.assertEqual(
            resolve_lower_context_limit_from_error(text, 256_000),
            131_072,
        )


if __name__ == "__main__":
    unittest.main()
