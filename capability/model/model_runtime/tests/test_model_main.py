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


if __name__ == "__main__":
    unittest.main()
