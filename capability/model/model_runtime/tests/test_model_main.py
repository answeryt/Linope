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


if __name__ == "__main__":
    unittest.main()
