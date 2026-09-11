"""Tests for context_defaults.py, including a live lip-composed model call."""

from __future__ import annotations

import importlib.util
import unittest

from plugins.model.model_API.model_paramaters.fallback_handlers.context_defaults import (
    DEFAULT_FALLBACK_CONTEXT,
    resolve_default_context_length,
)
from plugins.model.model_API.model_paramaters.fallback_handlers.test.live_model import (
    API_KEY,
    ask_live_model,
)


class ContextDefaultsTest(unittest.IsolatedAsyncioTestCase):
    def test_prefers_the_longest_matching_model_name(self) -> None:
        self.assertEqual(
            resolve_default_context_length("vendor/minimax-m3-latest"),
            1_000_000,
        )
        self.assertEqual(resolve_default_context_length("MINIMAX-legacy"), 204_800)

    def test_unknown_model_uses_fallback(self) -> None:
        self.assertEqual(
            resolve_default_context_length("unknown-provider/model"),
            DEFAULT_FALLBACK_CONTEXT,
        )

    @unittest.skipUnless(API_KEY, "OPENAI_API_KEY is not set")
    async def test_live_model_name_resolves_to_catalog_context(self) -> None:
        if importlib.util.find_spec("openai") is None:
            self.skipTest("openai package is not installed")
        text = await ask_live_model(
            "Reply with exactly this model identifier and nothing else: grok-4.3"
        )
        self.assertIn("grok-4.3", text.lower(), msg=text)
        self.assertEqual(resolve_default_context_length(text), 1_000_000)


if __name__ == "__main__":
    unittest.main()
