# -*- coding: utf-8 -*-

from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path
from typing import Any

from kernel.compose.capability import Capability
from kernel.compose.capability import CapabilityCatalog
from kernel.compose.capability import CapabilityGraphResolver
from kernel.compose.capability import ComposeResolutionError
from kernel.compose.capability import ComposeSpec
from kernel.compose.capability import inject_capabilities
from kernel.compose.capability.discovery.contracts import PluginDescriptor
from kernel.compose.capability.discovery.contracts import parse_requirements
from kernel.compose.capability.discovery.sources import ComposeCoreSource


ROOT = Path(__file__).resolve().parents[2]


class ResourcePool:
    def __init__(self) -> None:
        self.released: list[dict[str, Any]] = []

    async def acquire(
        self,
        resource_name: str,
        owner_id: str,
        amount: int | float,
    ) -> dict[str, Any]:
        return {
            "resource_name": resource_name,
            "owner_id": owner_id,
            "amount": amount,
        }

    async def release(self, lease: dict[str, Any]) -> dict[str, Any]:
        self.released.append(dict(lease))
        return {**lease, "state": "released"}


class ComposeRuntimeCompilerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.lip = inject_capabilities(repo=ROOT)
        compiler = self.lip.get("kernel_compose_runtime")
        self.lip_compose_runtime = compiler.compile_runtime(
            definition=self.lip.get("kernel_compose_definition"),
            executor=self.lip.get("kernel_compose_executor"),
            binding=self.lip.get("kernel_compose_binding"),
        )

    def tearDown(self) -> None:
        self.lip.unload()

    def test_raw_leaf_modules_do_not_need_apply(self) -> None:
        definition = self.lip.get("kernel_compose_definition")

        self.assertEqual(definition.PLUGIN_NAME, "kernel_compose_definition")
        self.assertFalse(hasattr(definition, "apply"))
        self.assertIs(definition, self.lip.get("kernel_compose_definition"))

    def test_compiler_registers_and_executes_composes(self) -> None:
        self.lip_compose_runtime.define("double", lambda value: value * 2)

        result = asyncio.run(self.lip_compose_runtime.execute("double", 3))

        self.assertEqual(result, 6)

    def test_runtime_decorator_uses_definition_api_and_registers(self) -> None:
        @self.lip_compose_runtime(
            retry={"max_attempts": 3},
            timeout=30,
            requires=["gpu"],
        )
        async def generate(input):
            return input

        pool = ResourcePool()
        result = asyncio.run(
            self.lip_compose_runtime.execute("generate", "content", resources=pool)
        )

        self.assertEqual(result, "content")
        self.assertEqual(self.lip_compose_runtime.require("generate")["requires"], ["gpu"])
        self.assertEqual(len(pool.released), 1)
        self.assertIs(
            self.lip_compose_runtime.require("generate")["handlers"]["generate"],
            generate,
        )

    def test_compiler_executes_named_interface(self) -> None:
        self.lip_compose_runtime.define(
            "worker",
            {
                "run": lambda value: f"run:{value}",
                "stop": lambda value: f"stop:{value}",
            },
            interfaces={
                "run": {"input_schema": "value"},
                "stop": {"input_schema": "value"},
            },
        )

        result = asyncio.run(
            self.lip_compose_runtime.execute("worker", "now", interface="stop")
        )
        definition = self.lip_compose_runtime.require("worker")

        self.assertEqual(result, "stop:now")
        self.assertEqual(
            definition["interfaces"]["stop"]["input_schema"], "value"
        )

    def test_compiler_delegates_binding_lifecycle(self) -> None:
        pool = ResourcePool()
        binding = self.lip_compose_runtime.build_binding(
            {"name": "worker", "requires": ["gpu"]},
            "process-1",
        )

        bound = asyncio.run(self.lip_compose_runtime.bind(binding, pool))
        bound_state = bound["state"]
        released = asyncio.run(self.lip_compose_runtime.release(bound, pool))

        self.assertEqual(bound_state, "bound")
        self.assertEqual(bound["compose"]["name"], "worker")
        self.assertNotIn("thread", bound)
        self.assertEqual(released["state"], "released")
        self.assertEqual(len(pool.released), 1)

    def test_user_controls_runtime_service_name_and_lifecycle(self) -> None:
        scoped = self.lip.bind("application")
        scoped.provide("lip_compose_runtime", self.lip_compose_runtime)

        self.assertIs(scoped.get("lip_compose_runtime"), self.lip_compose_runtime)

        scoped.unload("application")

        with self.assertRaises(LookupError):
            scoped.get("lip_compose_runtime")

    def test_full_unload_releases_injected_capabilities(self) -> None:
        self.assertTrue(self.lip.has_service("compose.definition"))

        self.lip.unload()

        self.assertFalse(self.lip.has_service("compose.definition"))

    def test_socket_cannot_be_used_for_composition(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            composition = Path(directory) / "composition.yaml"
            composition.write_text(
                "sockets: {}\n"
                "plugins:\n"
                "  - name: legacy\n"
                "    socket: exec_command\n",
                encoding="utf-8",
            )

            with self.assertRaises(Exception) as raised:
                inject_capabilities(composition, repo=ROOT)

        self.assertEqual(type(raised.exception).__name__, "CapabilityLoadError")
        self.assertIn("composition files are no longer supported", str(raised.exception))


class CompositionCapabilityGraphTest(unittest.TestCase):
    def test_compose_runtime_can_be_resolved_as_capability_graph(self) -> None:
        catalog = CapabilityCatalog.discover(ComposeCoreSource(ROOT))
        spec = ComposeSpec(
            "compose-runtime",
            ["compose.runtime"],
            entry="compose.runtime",
        )

        graph = CapabilityGraphResolver(catalog).resolve(spec)

        self.assertEqual(
            [node.name for node in graph.order()],
            [
                "kernel_compose_definition",
                "kernel_compose_executor",
                "kernel_compose_binding",
                "kernel_compose_runtime",
            ],
        )

        lip = inject_capabilities(repo=ROOT)
        try:
            composition = CapabilityGraphResolver(catalog).plan(spec).execute(lip)
            runtime = composition.target
            runtime.define("double", lambda value: value * 2)

            result = asyncio.run(runtime.execute("double", 3))

            self.assertEqual(result, 6)
            self.assertIs(lip.get("compose.runtime"), runtime)
        finally:
            lip.unload()

    def test_resolver_builds_graph_before_injection_then_returns_callable_composition(self) -> None:
        class Generate(Capability):
            name = "model_generate"
            kind = "model.generate"
            provides = ("model.generate",)

            def activate(self, context):
                context.provide("model.generate", lambda value: f"generated:{value}")

        class Streaming(Capability):
            name = "model_streaming"
            kind = "model.streaming"
            provides = ("model.streaming",)
            requires = ("model.generate",)

            def activate(self, context):
                generate = context.get("model.generate")
                context.provide("model.thread", lambda value: f"stream:{generate(value)}")

        catalog = CapabilityCatalog.from_plugins((Generate, Streaming))
        spec = ComposeSpec(
            "model-composition",
            ["model.streaming"],
            entry="model.thread",
        )
        graph = CapabilityGraphResolver(catalog).resolve(spec)

        self.assertEqual(
            [node.name for node in graph.order()],
            ["model_generate", "model_streaming"],
        )

        lip = inject_capabilities(repo=ROOT)
        try:
            composition = CapabilityGraphResolver(catalog).plan(spec).execute(lip)

            self.assertEqual(composition("input"), "stream:generated:input")
        finally:
            lip.unload()

    def test_matching_uses_constraints_without_importing_plugins(self) -> None:
        catalog = CapabilityCatalog.from_descriptors(
            [
                PluginDescriptor.from_mapping(
                    {
                        "name": "anthropic_chat",
                        "source": __file__,
                        "kind": "recipe",
                        "provides": ["model.chat"],
                        "constraints": {"provider": "anthropic"},
                    }
                ),
                PluginDescriptor.from_mapping(
                    {
                        "name": "openai_chat",
                        "source": __file__,
                        "kind": "recipe",
                        "provides": ["model.chat"],
                        "constraints": {
                            "provider": "openai",
                            "context_length": {"max": 128000},
                        },
                    }
                ),
            ]
        )
        spec = ComposeSpec(
            "openai-model-composition",
            ["model.chat"],
            constraints={"provider": "openai", "context_length": {"min": 64000}},
        )

        graph = CapabilityGraphResolver(catalog).resolve(spec)

        self.assertEqual([node.name for node in graph.nodes], ["openai_chat"])

    def test_many_cardinality_selects_all_providers(self) -> None:
        catalog = CapabilityCatalog.from_descriptors(
            [
                PluginDescriptor.from_mapping(
                    {
                        "name": "sampling",
                        "source": __file__,
                        "kind": "recipe",
                        "provides": ["model.parameters", "model.parameters.sampling"],
                    }
                ),
                PluginDescriptor.from_mapping(
                    {
                        "name": "tools",
                        "source": __file__,
                        "kind": "recipe",
                        "provides": ["model.parameters", "model.parameters.tools"],
                    }
                ),
            ]
        )
        spec = ComposeSpec(
            "params",
            [{"capability": "model.parameters", "cardinality": "many"}],
        )

        graph = CapabilityGraphResolver(catalog).resolve(spec)

        self.assertEqual(
            sorted(node.name for node in graph.nodes),
            ["sampling", "tools"],
        )

    def test_resolution_error_explains_missing_requirement(self) -> None:
        catalog = CapabilityCatalog.from_descriptors(())
        spec = ComposeSpec("model-composition", ["model.streaming"])

        with self.assertRaises(ComposeResolutionError) as raised:
            CapabilityGraphResolver(catalog).resolve(spec)

        self.assertIn("model.streaming", str(raised.exception))

    def test_parse_requirements_rejects_missing_capability(self) -> None:
        with self.assertRaises(ValueError):
            parse_requirements([{"cardinality": "many"}])

    def test_catalog_list_matches_kind_cluster(self) -> None:
        catalog = CapabilityCatalog.from_descriptors(
            [
                PluginDescriptor.from_mapping(
                    {
                        "name": "window",
                        "source": __file__,
                        "kind": "context.compression",
                        "provides": ["context.compression.window"],
                    }
                )
            ]
        )

        self.assertEqual([node.name for node in catalog.list("context")], ["window"])

    def test_get_all_uses_provides_aliases(self) -> None:
        lip = inject_capabilities(repo=ROOT)
        try:
            lip.provide("model.parameters.sampling", "sampling", aliases=["model.parameters"])
            lip.provide("model.parameters.tools", "tools", aliases=["model.parameters"])
            self.assertEqual(lip.get_all("model.parameters"), ("sampling", "tools"))
        finally:
            lip.unload()


if __name__ == "__main__":
    unittest.main()
