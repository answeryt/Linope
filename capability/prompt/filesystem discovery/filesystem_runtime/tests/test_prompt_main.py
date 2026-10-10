# -*- coding: utf-8 -*-
"""plugin-unit: load prompt_main by file, never through Host."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


def _load():
    path = Path(__file__).resolve().parents[1] / "prompt_main.py"
    spec = importlib.util.spec_from_file_location("prompt_main_runtime_leaf", path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class PromptMainTest(unittest.TestCase):
    def test_main_sends_only_the_user_message(self) -> None:
        main = _load()
        captured: dict[str, object] = {}

        def assemble_prompt(**kwargs):
            captured.update(kwargs)
            return {
                "system": "sys",
                "transient": "",
                "user": kwargs["user_content"],
            }

        runtime = SimpleNamespace(assemble_prompt=assemble_prompt)
        with patch.object(main, "_load_runtime", return_value=runtime):
            with patch("sys.stdout", new_callable=StringIO) as stdout:
                code = main.main(["hello", "there"])
        self.assertEqual(code, 0)
        self.assertEqual(captured["user_content"], "hello there")
        self.assertEqual(captured["memory_context"], "")
        self.assertEqual(captured["plugin_context"], "")
        self.assertEqual(captured["gateway_context"], "")
        self.assertNotIn("system_builder", captured)
        output = stdout.getvalue()
        self.assertIn("sys", output)
        self.assertIn("hello there", output)


if __name__ == "__main__":
    unittest.main()
