# -*- coding: utf-8 -*-
"""plugin-unit: load model_interface by file, never through Host."""

from __future__ import annotations

import asyncio
import importlib.util
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch


ROOT = Path(__file__).resolve().parents[1]


def _load(name: str):
    path = ROOT / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"{name}_leaf", path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class OpenAIChatCallApiTest(unittest.TestCase):
    def setUp(self) -> None:
        self.leaf = _load("openai_chat")

    def test_skips_unset_and_maps_chat_fields(self) -> None:
        kwargs = self.leaf._request_kwargs(
            {
                "temperature": 0.2,
                "top_p": 0.9,
                "max_tokens": 128,
                "thinking_enable": False,
                "reasoning_effort": "high",
                "parallel_tool_calls": True,
                "tools": "UNSET",
                "voice": None,
            },
            stream=False,
            generate_kwargs=None,
            extra_body=None,
        )
        self.assertEqual(kwargs["temperature"], 0.2)
        self.assertEqual(kwargs["top_p"], 0.9)
        self.assertEqual(kwargs["max_completion_tokens"], 128)
        self.assertNotIn("reasoning_effort", kwargs)
        self.assertNotIn("tools", kwargs)
        self.assertNotIn("stream_options", kwargs)

    def test_stream_tools_voice_and_extra(self) -> None:
        tools = [{"type": "function", "function": {"name": "lookup"}}]
        kwargs = self.leaf._request_kwargs(
            {
                "thinking_enable": True,
                "reasoning_effort": "high",
                "parallel_tool_calls": False,
                "tools": tools,
                "tool_choice": "auto",
                "voice": "alloy",
            },
            stream=True,
            generate_kwargs={"seed": 1},
            extra_body={"foo": "bar"},
        )
        self.assertEqual(kwargs["tools"], tools)
        self.assertEqual(kwargs["tool_choice"], "auto")
        self.assertEqual(kwargs["reasoning_effort"], "high")
        self.assertEqual(kwargs["parallel_tool_calls"], False)
        self.assertEqual(kwargs["stream_options"], {"include_usage": True})
        self.assertEqual(kwargs["modalities"], ["text", "audio"])
        self.assertEqual(kwargs["audio"], {"voice": "alloy", "format": "pcm16"})
        self.assertEqual(kwargs["seed"], 1)
        self.assertEqual(kwargs["extra_body"], {"foo": "bar"})

    def test_call_api_uses_lazy_sdk(self) -> None:
        create = AsyncMock(return_value="ok")
        client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        with patch.dict("sys.modules", {"openai": SimpleNamespace(AsyncClient=lambda **_: client)}):
            result = asyncio.run(
                self.leaf.call_api(
                    {
                        "api_key": "k",
                        "organization": None,
                        "base_url": None,
                        "model": "m",
                        "messages": [{"role": "user", "content": "hi"}],
                        "stream": False,
                        "client_kwargs": {},
                        "parameters": {"max_tokens": 8},
                    }
                )
            )
        self.assertEqual(result, "ok")
        create.assert_awaited_once()
        self.assertEqual(create.await_args.kwargs["max_completion_tokens"], 8)

    def test_formats_text_blocks(self) -> None:
        block = SimpleNamespace(type="text", text="hello")
        messages = self.leaf.format_messages([block])
        self.assertEqual(
            messages,
            [{"role": "user", "content": [{"type": "text", "text": "hello"}]}],
        )

    def test_parse_response_reads_choice_content(self) -> None:
        result = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="pong"))]
        )
        self.assertEqual(self.leaf.parse_response(result), "pong")

    def test_call_api_retries_context_limit_error(self) -> None:
        calls: list[dict] = []

        async def create(**kwargs):
            calls.append(kwargs)
            if len(calls) == 1:
                raise RuntimeError("max_model_len is 65536")
            return "ok"

        client = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=create))
        )
        with patch.dict(
            "sys.modules",
            {"openai": SimpleNamespace(AsyncClient=lambda **_: client)},
        ):
            result = asyncio.run(
                self.leaf.call_api(
                    {
                        "api_key": "k",
                        "organization": None,
                        "base_url": None,
                        "model": "m",
                        "messages": [{"role": "user", "content": "hi"}],
                        "stream": False,
                        "client_kwargs": {},
                        "parameters": {},
                    }
                )
            )
        self.assertEqual(result, "ok")
        self.assertEqual(len(calls), 2)


class OpenAIResponseCallApiTest(unittest.TestCase):
    def test_max_tokens_becomes_max_output_tokens(self) -> None:
        leaf = _load("openai_response")
        kwargs = leaf._request_kwargs({"max_tokens": 256}, stream=False, generate_kwargs=None, extra_body=None)
        self.assertEqual(kwargs["max_output_tokens"], 256)
        self.assertNotIn("max_completion_tokens", kwargs)


class GeminiCallApiTest(unittest.TestCase):
    def test_config_uses_max_output_tokens(self) -> None:
        leaf = _load("gemini")
        config = leaf._config({"max_tokens": 256, "temperature": 0.1}, None, None)
        self.assertEqual(config["max_output_tokens"], 256)
        self.assertEqual(config["temperature"], 0.1)

    def test_format_messages_maps_assistant_to_model(self) -> None:
        leaf = _load("gemini")
        formatted = leaf.format_messages([{"role": "assistant", "content": "hi"}])
        self.assertEqual(formatted[0]["role"], "model")
        self.assertEqual(formatted[0]["parts"], [{"text": "hi"}])


class AnthropicCallApiTest(unittest.TestCase):
    def test_request_kwargs_skip_unset(self) -> None:
        leaf = _load("anthropic")
        kwargs = leaf._request_kwargs(
            {"temperature": "UNSET", "top_p": 0.5, "tools": None},
            None,
            None,
        )
        self.assertEqual(kwargs, {"top_p": 0.5})

    def test_call_api_uses_card_max_tokens(self) -> None:
        leaf = _load("anthropic")
        create = AsyncMock(return_value="ok")
        client = SimpleNamespace(messages=SimpleNamespace(create=create))
        with patch.dict(
            "sys.modules",
            {"anthropic": SimpleNamespace(AsyncAnthropic=lambda **_: client)},
        ):
            asyncio.run(
                leaf.call_api(
                    {
                        "api_key": "k",
                        "base_url": None,
                        "model": "claude-opus-5",
                        "messages": [{"role": "user", "content": "hi"}],
                        "stream": False,
                        "client_kwargs": {},
                        "parameters": {"max_tokens": 128000},
                    }
                )
            )
        self.assertEqual(create.await_args.kwargs["max_tokens"], 128000)
        self.assertNotIn("tokens/tokens.py", leaf._PARAM_CACHE)

    def test_call_api_requires_max_tokens_when_unset(self) -> None:
        leaf = _load("anthropic")
        create = AsyncMock(return_value="ok")
        client = SimpleNamespace(messages=SimpleNamespace(create=create))
        with patch.dict(
            "sys.modules",
            {"anthropic": SimpleNamespace(AsyncAnthropic=lambda **_: client)},
        ):
            with self.assertRaisesRegex(ValueError, "requires max_tokens"):
                asyncio.run(
                    leaf.call_api(
                        {
                            "api_key": "k",
                            "base_url": None,
                            "model": "claude-opus-5",
                            "messages": [{"role": "user", "content": "hi"}],
                            "stream": False,
                            "client_kwargs": {},
                            "parameters": {"max_tokens": "UNSET"},
                        }
                    )
                )
        create.assert_not_awaited()
        self.assertNotIn("tokens/tokens.py", leaf._PARAM_CACHE)


if __name__ == "__main__":
    unittest.main()
