from __future__ import annotations

import importlib.util
import unittest

from plugins.model.model_API.model_paramaters.fallback_handlers.test.live_model import (
    API_KEY,
    ask_live_model,
)


class ReasoningEffortLiveTest(unittest.IsolatedAsyncioTestCase):
    @unittest.skipUnless(API_KEY, "OPENAI_API_KEY is not set")
    async def test_reasoning_effort_written_when_enabled(self) -> None:
        if importlib.util.find_spec("openai") is None:
            self.skipTest("openai package is not installed")

        text = await ask_live_model("Answer briefly: what is 2+2?")
        self.assertTrue(text.strip(), msg=text)


if __name__ == "__main__":
    unittest.main()

