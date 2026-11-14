# -*- coding: utf-8 -*-
"""plugin-unit: load model_main by file, never through Host."""

from __future__ import annotations

import importlib.util
import unittest
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch


def _load():
    path = Path(__file__).resolve().parents[1] / "model_main.py"
    spec = importlib.util.spec_from_file_location("model_main_runtime_leaf", path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ModelMainTest(unittest.TestCase):
    def test_main_sends_only_the_user_message(self) -> None:
        main = _load()
        reply = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="pong"))]
        )
        runtime = SimpleNamespace(
            MODEL_ROOT=Path(__file__).resolve().parents[2],
            call_model=AsyncMock(return_value=reply),
            load_interface=lambda _card: SimpleNamespace(
                parse_response=lambda result: result.choices[0].message.content,
                parse_stream_chunk=lambda _chunk: "",
            ),
        )
        with patch.object(main, "_load_runtime", return_value=runtime):
            with patch("sys.stdout", new_callable=StringIO) as stdout:
                code = main.main(["hello", "there"])
        self.assertEqual(code, 0)
        kwargs = runtime.call_model.await_args.kwargs
        messages = kwargs["messages"]
        self.assertEqual(messages, [{"role": "user", "content": "hello there"}])
        self.assertEqual({item["role"] for item in messages}, {"user"})
        self.assertNotIn("context", kwargs)
        self.assertNotIn("stream", kwargs)
        self.assertNotIn("model", kwargs)
        self.assertNotIn("base_url", kwargs)
        self.assertIn("pong", stdout.getvalue())

    def test_permission_is_not_forwarded_to_the_model(self) -> None:
        import asyncio

        main = _load()
        runtime = SimpleNamespace(
            call_model=AsyncMock(return_value="ok"),
            load_interface=lambda _card: SimpleNamespace(parse_response=lambda result: result),
        )
        with patch("capability.model.model_runtime.call_model.call_model", runtime.call_model):
            with patch("capability.model.model_runtime.call_model.load_interface", runtime.load_interface):
                result = asyncio.run(
                    main.load_named_card_async(
                        "openai_chat_model",
                        "message",
                        "hello",
                        {"permission": "read-only", "capabilities": ["read"], "temperature": 0.2},
                    )
                )
        self.assertEqual(result, "ok")
        kwargs = runtime.call_model.await_args.kwargs
        self.assertNotIn("permission", kwargs)
        self.assertNotIn("capabilities", kwargs)
        self.assertEqual(kwargs["temperature"], 0.2)

    def test_a_tool_call_keeps_its_structure(self) -> None:
        import asyncio

        main = _load()
        turn = {
            "type": "model_turn",
            "blocks": [
                {"type": "text", "text": "reading"},
                {"type": "tool-call", "id": "call-1", "name": "tools.read", "arguments": {"file_path": "a.py"}},
            ],
            "finish_reason": "tool_calls",
        }
        runtime = SimpleNamespace(
            call_model=AsyncMock(return_value=turn),
            load_interface=lambda _card: SimpleNamespace(
                parse_response_turn=lambda result: result,
                parse_response=lambda result: None,
            ),
        )
        with patch("capability.model.model_runtime.call_model.call_model", runtime.call_model):
            with patch("capability.model.model_runtime.call_model.load_interface", runtime.load_interface):
                result = asyncio.run(
                    main.load_named_card_async(
                        "openai_chat_model",
                        "message",
                        {"messages": [{"role": "user", "content": "read a.py"}], "tools": [{"name": "tools.read"}]},
                    )
                )
        self.assertIsInstance(result, dict)
        self.assertEqual(result["blocks"][1]["name"], "tools.read")
        self.assertEqual(result["blocks"][0]["text"], "reading")

    def test_a_fragment_goes_to_structured_notice(self) -> None:
        import asyncio

        main = _load()

        class _Chunks:
            def __init__(self) -> None:
                self._sent = False

            def __aiter__(self) -> "_Chunks":
                return self

            async def __anext__(self) -> dict:
                if self._sent:
                    raise StopAsyncIteration
                self._sent = True
                return {"type": "text-delta", "text": "hi"}

        runtime = SimpleNamespace(
            call_model=AsyncMock(return_value=_Chunks()),
            load_interface=lambda _card: SimpleNamespace(
                parse_stream_parts=lambda chunk: [chunk],
            ),
        )
        with patch("capability.model.model_runtime.call_model.call_model", runtime.call_model):
            with patch("capability.model.model_runtime.call_model.load_interface", runtime.load_interface):
                with patch(
                    "kernel.process.process_runtime.runtime.emit_notice"
                ) as emit_notice:
                    result = asyncio.run(
                        main.load_named_card_async("openai_chat_model", "message", "hello")
                    )
        emit_notice.assert_called_once_with({"kind": "model.delta", "text": "hi"})
        self.assertEqual(result["blocks"][0]["text"], "hi")


if __name__ == "__main__":
    unittest.main()
