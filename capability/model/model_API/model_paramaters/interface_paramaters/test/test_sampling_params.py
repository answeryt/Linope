from __future__ import annotations

import importlib.util
import unittest

from plugins.model.model_API.model_paramaters.fallback_handlers.test.live_model import (
    API_KEY,
    ask_live_model,
)


class SamplingParamsLiveTest(unittest.IsolatedAsyncioTestCase):
    @unittest.skipUnless(API_KEY, "OPENAI_API_KEY is not set")
    async def test_sampling_params_temperature_top_p_max_tokens(self) -> None:
        if importlib.util.find_spec("openai") is None:
            self.skipTest("openai package is not installed")

        text = await ask_live_model("Reply with exactly one short word: pong.")
        self.assertTrue(text.strip(), msg=text)


if __name__ == "__main__":
    unittest.main()

