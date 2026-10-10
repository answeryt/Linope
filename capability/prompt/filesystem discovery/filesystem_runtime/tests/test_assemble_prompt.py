# -*- coding: utf-8 -*-
"""plugin-unit: load assemble_prompt by file, never through Host."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


def _load():
    path = Path(__file__).resolve().parents[1] / "filesystem_prompt_load.py"
    spec = importlib.util.spec_from_file_location("assemble_prompt_runtime_leaf", path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class AssemblePromptTest(unittest.TestCase):
    def setUp(self) -> None:
        self.runtime = _load()
        self.runtime._LEAF_CACHE.clear()

    def test_injected_builders_do_not_load_leaves(self) -> None:
        assembled = self.runtime.assemble_prompt(
            user_content="hello",
            memory_context="note",
            system_builder=lambda context=None: "sys",
            transient_builder=lambda content, **_kwargs: f"{content}\n\nnote",
        )
        self.assertEqual(assembled["system"], "sys")
        self.assertEqual(assembled["user"], "hello\n\nnote")
        self.assertEqual(self.runtime._LEAF_CACHE, {})

    def test_default_path_injects_loader_plugin_into_builder(self) -> None:
        builder = SimpleNamespace(
            build_system_prompt=lambda context=None, plugin=None: (
                "from-plugin" if plugin is not None else "missing"
            ),
        )
        loader = SimpleNamespace(SYSTEM_PROMPT_PLUGIN=object())
        transient = SimpleNamespace(
            TRANSIENT_PROMPT_BUILDER_PLUGIN=SimpleNamespace(
                build_context=lambda **_kwargs: "suffix",
            ),
            build_transient_prompt=lambda content, **_kwargs: f"{content}\n\nsuffix",
        )

        def load(path):
            resolved = Path(path)
            if resolved == self.runtime.SYSTEM_BUILDER_LEAF.resolve():
                return builder
            if resolved == self.runtime.SYSTEM_LOAD_LEAF.resolve():
                return loader
            if resolved == self.runtime.TRANSIENT_BUILDER_LEAF.resolve():
                return transient
            raise AssertionError(f"unexpected leaf {resolved}")

        with patch.object(self.runtime, "_load_leaf", side_effect=load):
            assembled = self.runtime.assemble_prompt(user_content="ask")
        self.assertEqual(assembled["system"], "from-plugin")
        self.assertEqual(assembled["transient"], "suffix")
        self.assertEqual(assembled["user"], "ask\n\nsuffix")

    def test_non_string_system_raises(self) -> None:
        with self.assertRaises(TypeError):
            self.runtime.assemble_prompt(
                system_builder=lambda context=None: None,
                transient_builder=lambda content, **_kwargs: content,
            )

    def test_default_path_uses_prompt_card_via_loader_leaf(self) -> None:
        assembled = self.runtime.assemble_prompt(user_content="ask")
        self.assertIn("Role", assembled["system"])
        self.assertEqual(assembled["user"], "ask")


if __name__ == "__main__":
    unittest.main()
