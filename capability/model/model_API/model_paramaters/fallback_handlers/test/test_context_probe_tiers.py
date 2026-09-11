"""Tests for context_probe_tiers.py, including a live lip-composed model call."""

from __future__ import annotations

import importlib.util
import re
import unittest

from plugins.model.model_API.model_paramaters.fallback_handlers.context_probe_tiers import (
    get_next_context_probe_tier,
)
from plugins.model.model_API.model_paramaters.fallback_handlers.test.live_model import (
    API_KEY,
    ask_live_model,
)


class ContextProbeTiersTest(unittest.IsolatedAsyncioTestCase):
    def test_returns_the_next_strictly_lower_tier(self) -> None:
        cases = (
            (300_000, 256_000),
            (256_000, 128_000),
            (129_000, 128_000),
            (128_000, 64_000),
            (8_001, 8_000),
        )
        for current, expected in cases:
            with self.subTest(current=current):
                self.assertEqual(get_next_context_probe_tier(current), expected)

    def test_returns_none_at_or_below_the_smallest_tier(self) -> None:
        self.assertIsNone(get_next_context_probe_tier(8_000))
        self.assertIsNone(get_next_context_probe_tier(1_000))

    @unittest.skipUnless(API_KEY, "OPENAI_API_KEY is not set")
    async def test_live_length_selects_next_probe_tier(self) -> None:
        if importlib.util.find_spec("openai") is None:
            self.skipTest("openai package is not installed")
        text = await ask_live_model(
            "Reply with exactly this integer and nothing else: 300000"
        )
        match = re.search(r"\b300000\b", text)
        self.assertIsNotNone(match, msg=text)
        current_length = int(match.group(0))
        self.assertEqual(get_next_context_probe_tier(current_length), 256_000)


if __name__ == "__main__":
    unittest.main()
