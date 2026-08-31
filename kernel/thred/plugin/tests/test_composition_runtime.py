# -*- coding: utf-8 -*-

from __future__ import annotations

import asyncio
import json
import tempfile
import unittest
from pathlib import Path

from kernel.thred.plugin.host import (
    Assembler,
    Context,
    FileSystemSource,
    PluginState,
    PythonPluginSource,
    StaticSnapshotSource,
    load_composition,
)


class PluginCompositionRuntimeTest(unittest.TestCase):
    def test_legacy_python_source_indexes_existing_plugins_without_importing(self) -> None:
        root = Path(__file__).resolve().parents[4] / "plugins"
        descriptors = list(PythonPluginSource([root]).discover())
        by_name = {item.artifact.name: item for item in descriptors}

        self.assertGreaterEqual(len(descriptors), 70)
        self.assertEqual(by_name["read"].artifact.kind, "tool")
        self.assertEqual(by_name["sandbox_provider"].artifact.kind, "capability")

    def test_dependency_change_unloads_and_reactivates_consumer(self) -> None:
        ctx = Context()
        events: list[str] = []

        def consumer(plugin_ctx, _config):
            events.append(f"load:{plugin_ctx.get('database')}")
            return lambda: events.append("unload")

        consumer_fiber = ctx.plugin(
            consumer,
            name="consumer",
            requirements=["database"],
        )
        self.assertEqual(consumer_fiber.state, PluginState.PENDING)

        def database(plugin_ctx, config):
            plugin_ctx.provide("database", config)

        first = ctx.plugin(database, "first", name="database-first")
        self.assertEqual(consumer_fiber.state, PluginState.ACTIVE)
        self.assertEqual(events, ["load:first"])

        first.dispose()
        self.assertEqual(consumer_fiber.state, PluginState.PENDING)
        self.assertEqual(events, ["load:first", "unload"])

        ctx.plugin(database, "second", name="database-second")
        self.assertEqual(consumer_fiber.state, PluginState.ACTIVE)
        self.assertEqual(events, ["load:first", "unload", "load:second"])
        ctx.unload()

    def test_tool_manifest_is_discovered_bridged_and_unloaded(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plugin = root / "echo"
            plugin.mkdir()
            (plugin / "plugin.toml").write_text(
                '[plugin]\n'
                'name = "echo_tools"\n'
                'kind = "tool"\n'
                'source = "plugin.py"\n'
                'requires = ["tools"]\n',
                encoding="utf-8",
            )
            (plugin / "plugin.py").write_text(
                'PLUGIN_NAME = "echo_tools"\n'
                'PLUGIN_VERSION = "1.0"\n'
                'def tool_schemas():\n'
                '    return [{"name": "echo", "parameters": {"type": "object"}}]\n'
                'def dispatch(name, arguments, **kwargs):\n'
                '    return arguments["value"]\n',
                encoding="utf-8",
            )
            ctx = Context(repo=root)
            assembler = Assembler(ctx)
            fibers = assembler.mount_source(FileSystemSource([root]), strict=True)
            tools = ctx.get("tools")

            self.assertEqual(fibers[0].state, PluginState.ACTIVE)
            self.assertEqual(tools.dispatch("echo", {"value": "ok"}), "ok")
            self.assertEqual(tools.schemas()[0]["name"], "echo")

            fibers[0].dispose()
            with self.assertRaises(LookupError):
                tools.dispatch("echo", {"value": "missing"})
            ctx.unload()

    def test_composition_can_enable_dynamic_manifest_roots(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plugin = root / "plugins" / "sample"
            plugin.mkdir(parents=True)
            (plugin / "plugin.toml").write_text(
                '[plugin]\n'
                'name = "sample_capability"\n'
                'kind = "capability"\n'
                'source = "plugin.py"\n',
                encoding="utf-8",
            )
            (plugin / "plugin.py").write_text(
                'PLUGIN_NAME = "sample_capability"\n'
                'PLUGIN_VERSION = "1.0"\n'
                'VALUE = 42\n',
                encoding="utf-8",
            )
            composition = root / "composition.yaml"
            composition.write_text(
                "sources:\n"
                "  - type: manifest\n"
                "    roots: [plugins]\n"
                "    strict: true\n",
                encoding="utf-8",
            )

            ctx = load_composition(composition, repo=root)
            self.assertEqual(ctx.get("sample_capability").VALUE, 42)
            ctx.unload()

    def test_model_function_bridge_streams_one_normalized_result(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "model.py").write_text(
                'PLUGIN_NAME = "demo_model"\n'
                'PLUGIN_VERSION = "1.0"\n'
                'async def call_api(model, messages):\n'
                '    return {"model": model, "count": len(messages)}\n',
                encoding="utf-8",
            )
            snapshot = root / "plugins.json"
            snapshot.write_text(
                json.dumps(
                    {
                        "artifacts": [
                            {
                                "name": "demo_model",
                                "kind": "model",
                                "source": "model.py",
                                "provider": "demo",
                                "requires": ["llm"],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            ctx = Context(repo=root)
            Assembler(ctx).mount_source(StaticSnapshotSource(snapshot), strict=True)

            async def collect():
                stream = ctx.get("llm").stream(
                    {
                        "provider": "demo",
                        "model": "m",
                        "messages": [{"role": "user"}],
                    }
                )
                return [item async for item in stream]

            self.assertEqual(
                asyncio.run(collect()),
                [{"model": "m", "count": 1}],
            )
            ctx.unload()

    def test_pipeline_orders_capabilities_and_explicit_edges(self) -> None:
        ctx = Context()
        Assembler(ctx)
        pipelines = ctx.get("pipelines")
        owner = ctx.bind("pipeline-test")
        owner.get("pipelines").register(
            "finish",
            lambda value: value + ["finish"],
            requires=["normalized"],
        )
        owner.get("pipelines").register(
            "normalize",
            lambda value: value + ["normalize"],
            provides=["normalized"],
        )
        owner.get("pipelines").register(
            "audit",
            lambda value: value + ["audit"],
            after=["finish"],
        )

        self.assertEqual(
            pipelines.run([], ["finish", "audit", "normalize"]),
            ["normalize", "finish", "audit"],
        )
        ctx.unload()


if __name__ == "__main__":
    unittest.main()
