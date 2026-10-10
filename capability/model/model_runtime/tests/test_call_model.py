# -*- coding: utf-8 -*-
"""plugin-unit: load call_model by file, never through Host."""

from __future__ import annotations

import asyncio
import importlib.util
import os
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch


def _load():
    path = Path(__file__).resolve().parents[1] / "call_model.py"
    spec = importlib.util.spec_from_file_location("call_model_runtime_leaf", path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CallModelTest(unittest.TestCase):
    def setUp(self) -> None:
        self.runtime = _load()
        self.runtime._LEAF_CACHE.clear()

    def test_load_card_reads_json_model_name(self) -> None:
        card = self.runtime.load_card("openai_chat_model")
        self.assertEqual(card["interface"], "openai_chat")
        self.assertEqual(card["model"], "gpt-5.6-sol")
        self.assertEqual(card["stream"], True)
        self.assertEqual(card["base_url"], "https://eapi.site/v1")

    def test_unknown_card_raises(self) -> None:
        with self.assertRaises(FileNotFoundError):
            self.runtime.load_card("missing_model")

    def test_build_payload_uses_env_key_and_caller_messages(self) -> None:
        card = self.runtime.load_card("openai_chat_model")
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}, clear=False):
            payload = self.runtime.build_payload(
                card,
                messages=[{"role": "user", "content": "hi"}],
                temperature=0.2,
            )
        self.assertEqual(payload["api_key"], "sk-test")
        self.assertEqual(payload["messages"], [{"role": "user", "content": "hi"}])
        self.assertEqual(payload["parameters"]["temperature"], 0.2)
        self.assertTrue(payload["stream"])
        self.assertEqual(payload["client_kwargs"], {})
        self.assertEqual(payload["base_url"], "https://eapi.site/v1")

    def test_unset_stream_is_false_and_empty_base_url_is_none(self) -> None:
        card = self.runtime.load_card("gemini_model")
        with patch.dict(os.environ, {"GEMINI_API_KEY": "gk"}, clear=False):
            payload = self.runtime.build_payload(card, messages="ping")
        self.assertFalse(payload["stream"])
        self.assertIsNone(payload["base_url"])
        self.assertEqual(payload["messages"], ["ping"])

    def test_missing_api_key_raises(self) -> None:
        card = self.runtime.load_card("anthropic_model")
        env = {key: value for key, value in os.environ.items() if key != "ANTHROPIC_API_KEY"}
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaises(RuntimeError):
                self.runtime.build_payload(card, messages=[], api_key=None)

    def test_context_is_prepended(self) -> None:
        card = {
            "provider": "openai",
            "interface": "openai_chat",
            "model": "m",
            "api_key_env": "OPENAI_API_KEY",
        }
        with patch.dict(os.environ, {"OPENAI_API_KEY": "k"}):
            payload = self.runtime.build_payload(
                card,
                context=[{"role": "system", "content": "sys"}],
                messages=[{"role": "user", "content": "q"}],
            )
        self.assertEqual(
            payload["messages"],
            [
                {"role": "system", "content": "sys"},
                {"role": "user", "content": "q"},
            ],
        )

    def test_call_model_dispatches_to_interface(self) -> None:
        fake = SimpleNamespace(call_api=AsyncMock(return_value="ok"))
        original = self.runtime._load_leaf

        def load(path):
            resolved = Path(path)
            if resolved.parent == self.runtime.INTERFACE_ROOT:
                self.assertEqual(resolved.stem, "openai_chat")
                return fake
            return original(path)

        with patch.object(self.runtime, "_load_leaf", side_effect=load):
            result = asyncio.run(
                self.runtime.call_model(
                    "openai_chat_model",
                    messages=[{"role": "user", "content": "hi"}],
                    api_key="k",
                )
            )
        self.assertEqual(result, "ok")
        fake.call_api.assert_awaited_once()
        payload = fake.call_api.await_args.args[0]
        self.assertEqual(payload["model"], "gpt-5.6-sol")
        self.assertEqual(payload["messages"][0]["content"], "hi")


if __name__ == "__main__":
    unittest.main()
