# -*- coding: utf-8 -*-

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path
from types import ModuleType


ROOT = Path(__file__).resolve().parents[2]


def load(relative_path: str, module_name: str) -> ModuleType:
    path = ROOT / relative_path
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


definition = load(
    "kernel/resource/definition/resource_definition_plugin.py",
    "resource_definition_plugin_test",
)
pool_module = load(
    "kernel/resource/pool/resource_pool_plugin.py",
    "resource_pool_plugin_test",
)
compose_module = load(
    "kernel/compose/definition/compose_definition_plugin.py",
    "compose_plugin_test",
)
binding_module = load(
    "kernel/compose/binding/compose_binding_plugin.py",
    "compose_binding_plugin_test",
)


class ResourceThreadTest(unittest.IsolatedAsyncioTestCase):
    async def test_compose_container_and_model_resources(self) -> None:
        pool = pool_module.compose_resources(
            definition.define_resource("cpu", kind="container", capacity=2),
            definition.define_resource("context", kind="model", capacity=8),
        )
        snapshot = pool.snapshot()["resources"]
        self.assertEqual({"cpu", "context"}, set(snapshot))
        self.assertEqual("model", snapshot["context"]["kind"])

    async def test_capacity_rejection(self) -> None:
        pool = pool_module.ResourcePool()
        pool.register(definition.define_resource("gpu", capacity=2))

        await pool.acquire("gpu", "owner-a", 1.5)
        with self.assertRaises(pool_module.ResourceCapacityError):
            await pool.acquire("gpu", "owner-b", 1)

        snapshot = pool.snapshot()
        self.assertEqual(snapshot["resources"]["gpu"]["allocated"], 1.5)
        self.assertEqual(snapshot["resources"]["gpu"]["available"], 0.5)

    async def test_release_is_idempotent(self) -> None:
        release_calls: list[str] = []

        async def on_release(lease: dict[str, object]) -> None:
            release_calls.append(str(lease["lease_id"]))

        pool = pool_module.ResourcePool()
        pool.register(
            definition.define_resource(
                "sandbox", capacity=1, release=on_release
            )
        )
        lease = await pool.acquire("sandbox", "owner")

        first = await pool.release(lease)
        second = await pool.release(lease)

        self.assertEqual(first["state"], "released")
        self.assertEqual(second, first)
        self.assertEqual(release_calls, [lease["lease_id"]])
        self.assertEqual(
            pool.snapshot()["resources"]["sandbox"]["available"], 1
        )

    async def test_compose_decorator_and_registry(self) -> None:
        def stop() -> str:
            return "stop"

        @compose_module.compose(
            name="worker",
            handlers={"stop": stop},
            interfaces={
                "run": {"input_schema": "RunInput"},
                "stop": {"output_schema": "StopResult"},
            },
            requires=["context"],
            lifetime="compose",
        )
        def run() -> str:
            return "run"

        registry = compose_module.ComposeRegistry([run])
        stored = registry.require("worker")

        self.assertFalse(hasattr(compose_module, "define_task"))
        self.assertEqual(stored["kind"], "compose")
        self.assertEqual(set(stored["interfaces"]), {"run", "stop"})
        self.assertEqual(set(stored["handlers"]), {"run", "stop"})
        self.assertEqual(
            stored["interfaces"]["run"]["input_schema"], "RunInput"
        )
        self.assertEqual(stored["requires"], ["context"])

    async def test_compose_functions_bind_and_release_resources(self) -> None:
        def run() -> str:
            return "run"

        def stop() -> str:
            return "stop"

        compose = compose_module.define_compose(
            "worker",
            [run, stop],
            interfaces={"run": {}, "stop": {}},
            requires=["context", {"name": "tool", "amount": 2}],
            lifetime="compose",
            release_while_waiting=["tool"],
        )
        self.assertEqual(set(compose["interfaces"]), {"run", "stop"})
        self.assertEqual(compose["handlers"]["run"](), "run")

        pool = pool_module.ResourcePool()
        pool.register(definition.define_resource("context", capacity=1))
        pool.register(definition.define_resource("tool", capacity=2))
        binding = binding_module.build_binding(
            compose, process_id="process-1", binding_id="binding-1"
        )

        bound = await binding_module.bind_resources(binding, pool)
        self.assertEqual(bound["state"], "bound")
        self.assertEqual(bound["compose"]["name"], "worker")
        self.assertNotIn("thread", bound)
        self.assertEqual(len(bound["resource_leases"]), 2)
        self.assertTrue(
            all(
                lease["owner_id"] == "binding-1"
                for lease in bound["resource_leases"]
            )
        )

        released = await binding_module.release_resources(binding, pool)
        self.assertEqual(released["state"], "released")
        self.assertTrue(
            all(
                lease["state"] == "released"
                for lease in released["resource_leases"]
            )
        )
        snapshot = pool.snapshot()
        self.assertEqual(snapshot["resources"]["context"]["allocated"], 0)
        self.assertEqual(snapshot["resources"]["tool"]["allocated"], 0)


if __name__ == "__main__":
    unittest.main()
