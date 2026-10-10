"""The one capability forwarder uses existing entries and does not call providers."""

from __future__ import annotations

import asyncio
import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import capability.process_adapter as process_adapter
from capability.process_adapter import create_adapter
from kernel.process.process_creat.instances import adapter_module_path, describe_instance
from kernel.process.profile import load_declaration
from kernel.process.reconcile import ProcessReconciler
from kernel.resource.pool import ResourcePool
from kernel.process.ledger import FileResourceStore

_CAPABILITY_ROOT = Path(__file__).resolve().parents[3] / "capability"


def _forget_file_loaded_plugins() -> None:
    for name, module in list(sys.modules.items()):
        if name.startswith("capability."):
            continue
        raw = getattr(module, "__file__", None)
        if not raw:
            continue
        path = Path(raw).resolve()
        try:
            path.relative_to(_CAPABILITY_ROOT)
        except ValueError:
            continue
        if path.name == "process_adapter.py":
            continue
        del sys.modules[name]


def _load(relative: str):
    path = _CAPABILITY_ROOT / relative
    name = "adapter_probe_" + path.stem
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _context_with(**call_params: object) -> SimpleNamespace:
    return SimpleNamespace(grants=(SimpleNamespace(call_params=dict(call_params)),))


def _start(capability: str, tmp_path: Path, *, process_id: str):
    declaration, definition = load_declaration(capability, ())
    store = FileResourceStore(tmp_path / "resources.json")
    process = ProcessReconciler(ResourcePool(store)).start(
        declaration,
        process_id=process_id,
        definition=definition,
    )
    return store, process


class ProcessAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        _forget_file_loaded_plugins()

    def tearDown(self) -> None:
        _forget_file_loaded_plugins()

    def test_model_forward_keeps_the_card_object(self) -> None:
        plugin = _load("model/model_provider/openai_chat_model/openai_chat_model_plugin.py")
        seen: dict[str, object] = {}

        async def fake_call_model(card: object, **kwargs: object) -> str:
            seen["card"] = card
            seen["kwargs"] = kwargs
            return "forwarded"

        with (
            patch(
                "capability.model.model_runtime.call_model.call_model",
                fake_call_model,
            ),
            patch(
                "capability.model.model_runtime.call_model.load_interface",
                lambda card: SimpleNamespace(parse_response=lambda result: result),
            ),
        ):
            adapter = create_adapter()
            adapter.initialize(_context_with(temperature=0.2))
            result = adapter.handle(
                {
                    "operation": "load",
                    "kind": "prompt",
                    "body": "hello",
                }
            )
        self.assertEqual(result, "forwarded")
        self.assertEqual(seen["card"], "openai_chat_model")
        self.assertNotIsInstance(seen["card"], dict)
        self.assertEqual(
            seen["kwargs"],
            {
                "temperature": 0.2,
                "messages": [{"role": "user", "content": "hello"}],
            },
        )
        adapter.shutdown()

    def test_model_stream_uses_the_interface_chunk_parser(self) -> None:
        plugin = _load("model/model_provider/openai_chat_model/openai_chat_model_plugin.py")

        async def fake_call_model(card: object, **kwargs: object):
            del kwargs
            self.assertEqual(card, "openai_chat_model")

            async def chunks():
                yield "hi"
                yield ""
                yield "-there"

            return chunks()

        with (
            patch(
                "capability.model.model_runtime.call_model.call_model",
                fake_call_model,
            ),
            patch(
                "capability.model.model_runtime.call_model.load_interface",
                lambda card: SimpleNamespace(parse_stream_chunk=lambda chunk: chunk),
            ),
        ):
            adapter = create_adapter()
            adapter.initialize(_context_with())
            self.assertEqual(
                adapter.handle({"operation": "load", "kind": "prompt", "body": []}),
                "hi-there",
            )

    def test_model_async_forward_uses_the_process_event_loop(self) -> None:
        _load("model/model_provider/openai_chat_model/openai_chat_model_plugin.py")

        async def fake_call_model(card: object, **kwargs: object) -> str:
            self.assertEqual(card, "openai_chat_model")
            self.assertEqual(kwargs["messages"], [{"role": "user", "content": "hello"}])
            return "async-forwarded"

        with (
            patch(
                "capability.model.model_runtime.call_model.call_model",
                fake_call_model,
            ),
            patch(
                "capability.model.model_runtime.call_model.load_interface",
                lambda card: SimpleNamespace(parse_response=lambda result: result),
            ),
        ):
            adapter = create_adapter()
            adapter.initialize(_context_with(temperature=0.2))
            result = asyncio.run(
                adapter.handle_async(
                    {
                        "operation": "load",
                        "kind": "prompt",
                        "body": "hello",
                    }
                )
            )
        self.assertEqual(result, "async-forwarded")
        self.assertTrue(adapter.is_async)

    def test_tool_forward_reaches_dispatch(self) -> None:
        _load("tools/agent_tools/shell_tools/bash_plugin.py")
        adapter = create_adapter()
        adapter.initialize(_context_with())
        result = adapter.handle(
            {
                "operation": "load",
                "kind": "tool",
                "body": {"command": "", "description": "noop"},
            }
        )
        self.assertIn("invalid command", result)

    def test_adapter_does_not_open_cards_or_build_messages(self) -> None:
        text = Path(process_adapter.__file__).read_text(encoding="utf-8")
        self.assertNotIn("call_model", text)
        self.assertNotIn("CARD_CONFIG", text)
        self.assertNotIn('"role"', text)

    def test_context_load_reaches_the_matching_function(self) -> None:
        _load("context/context_compression/sliding_window/capability_profile.py")
        adapter = create_adapter()
        result = adapter.handle(
            {
                "operation": "load",
                "kind": "context",
                "body": {
                    "messages": [{"role": "user", "content": "hi"}],
                    "user_index": 0,
                },
            }
        )
        self.assertEqual(result, 1)

    def test_context_load_without_a_matching_function_is_rejected(self) -> None:
        _load("context/context_compression/sliding_window/capability_profile.py")
        adapter = create_adapter()
        with self.assertRaisesRegex(ValueError, "没有能装入这份内容的函数"):
            adapter.handle(
                {
                    "operation": "load",
                    "kind": "context",
                    "body": {},
                }
            )

    def test_every_instance_records_the_adapter_path(self) -> None:
        definition = describe_instance("tools.bash")
        self.assertEqual(
            Path(definition.module_paths[-1]).resolve(),
            adapter_module_path().resolve(),
        )
        self.assertNotIn(definition.module_paths[-1], definition.module_paths[:-1])

    def test_two_prompts_keep_the_same_model_entity(self) -> None:
        removed = os.environ.pop("OPENAI_API_KEY", None)
        try:
            with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as raw:
                store, process = _start(
                    "model.openai_chat_model",
                    Path(raw),
                    process_id="same-model-process",
                )
                try:
                    def entity_count() -> int:
                        return len(store.export_state()["sections"]["resource"]["entities"])

                    before = entity_count()
                    for text in ("请你甲", "请你乙"):
                        reply = process.send(
                            {"operation": "load", "kind": "prompt", "body": text},
                            timeout=20,
                        )
                        self.assertEqual(reply["event"], "error")
                        self.assertIn("API key", reply["error"])
                    self.assertEqual(entity_count(), before)
                    self.assertEqual(before, 1)
                    stored = store.activation_for("same-model-process")
                    self.assertNotIn("请你甲", str(stored))
                finally:
                    process.stop()
                    store.close()
        finally:
            if removed is not None:
                os.environ["OPENAI_API_KEY"] = removed

    def test_model_process_reports_the_existing_missing_key_error(self) -> None:
        removed = os.environ.pop("OPENAI_API_KEY", None)
        try:
            with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as raw:
                store, process = _start(
                    "model.openai_chat_model",
                    Path(raw),
                    process_id="model-adapter-process",
                )
                try:
                    reply = process.send(
                        {
                            "operation": "load",
                            "kind": "prompt",
                            "body": "hi",
                        },
                        timeout=20,
                    )
                    self.assertEqual(reply["event"], "error")
                    self.assertNotIn("No adapter is registered", reply["error"])
                    self.assertIn("API key", reply["error"])
                finally:
                    process.stop()
                    store.close()
        finally:
            if removed is not None:
                os.environ["OPENAI_API_KEY"] = removed

    def test_bash_process_reaches_the_existing_argument_error(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as raw:
            store, process = _start(
                "tools.bash",
                Path(raw),
                process_id="bash-adapter-process",
            )
            try:
                reply = process.send(
                    {
                        "operation": "load",
                        "kind": "tool",
                        "body": {"command": "", "description": "noop"},
                    },
                    timeout=20,
                )
                self.assertEqual(reply["event"], "result")
                self.assertIn("invalid command", reply["result"])
            finally:
                process.stop()
                store.close()

    def test_context_process_calls_a_pure_function(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as raw:
            store, process = _start(
                "context.sliding_window",
                Path(raw),
                process_id="context-adapter-process",
            )
            try:
                reply = process.send(
                    {
                        "operation": "load",
                        "kind": "context",
                        "body": {
                            "messages": [{"role": "user", "content": "hi"}],
                            "user_index": 0,
                        },
                    },
                    timeout=20,
                )
                self.assertEqual(reply["event"], "result")
                self.assertEqual(reply["result"], 1)
            finally:
                process.stop()
                store.close()

    def test_prompt_process_calls_assemble_prompt(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as raw:
            store, process = _start(
                "prompt.filesystem_discovery",
                Path(raw),
                process_id="prompt-adapter-process",
            )
            try:
                reply = process.send(
                    {
                        "operation": "load",
                        "kind": "prompt",
                        "body": "hello-from-process",
                    },
                    timeout=20,
                )
                self.assertEqual(reply["event"], "result")
                self.assertIn("hello-from-process", str(reply["result"]))
            finally:
                process.stop()
                store.close()
