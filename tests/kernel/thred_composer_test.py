# -*- coding: utf-8 -*-

from __future__ import annotations

import asyncio
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

from kernel.thred.plugin.host import load_composition


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


class ThredRuntimeCompilerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.lip = load_composition(repo=ROOT)
        compiler = self.lip.module("kernel_thred_runtime")
        self.lip_thred_runtime = compiler.compile_runtime(
            definition=self.lip.module("kernel_thred_definition"),
            executor=self.lip.module("kernel_thred_executor"),
            binding=self.lip.module("kernel_thred_binding"),
        )

    def tearDown(self) -> None:
        self.lip.unload()

    def test_raw_leaf_modules_do_not_need_apply(self) -> None:
        definition = self.lip.module("kernel_thred_definition")

        self.assertEqual(definition.PLUGIN_NAME, "kernel_thred_definition")
        self.assertFalse(hasattr(definition, "apply"))
        self.assertIs(definition, self.lip.module("kernel_thred_definition"))

    def test_compiler_registers_and_executes_threds(self) -> None:
        self.lip_thred_runtime.define("double", lambda value: value * 2)

        result = asyncio.run(self.lip_thred_runtime.execute("double", 3))

        self.assertEqual(result, 6)

    def test_runtime_decorator_uses_definition_api_and_registers(self) -> None:
        @self.lip_thred_runtime(
            retry={"max_attempts": 3},
            timeout=30,
            requires=["gpu"],
        )
        async def generate(input):
            return input

        pool = ResourcePool()
        result = asyncio.run(
            self.lip_thred_runtime.execute("generate", "content", resources=pool)
        )

        self.assertEqual(result, "content")
        self.assertEqual(self.lip_thred_runtime.require("generate")["requires"], ["gpu"])
        self.assertEqual(len(pool.released), 1)
        self.assertIs(
            self.lip_thred_runtime.require("generate")["handlers"]["generate"],
            generate,
        )

    def test_compiler_executes_named_interface(self) -> None:
        self.lip_thred_runtime.define(
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
            self.lip_thred_runtime.execute("worker", "now", interface="stop")
        )
        definition = self.lip_thred_runtime.require("worker")

        self.assertEqual(result, "stop:now")
        self.assertEqual(
            definition["interfaces"]["stop"]["input_schema"], "value"
        )

    def test_compiler_delegates_binding_lifecycle(self) -> None:
        pool = ResourcePool()
        binding = self.lip_thred_runtime.build_binding(
            {"name": "worker", "requires": ["gpu"]},
            "process-1",
        )

        bound = asyncio.run(self.lip_thred_runtime.bind(binding, pool))
        bound_state = bound["state"]
        released = asyncio.run(self.lip_thred_runtime.release(bound, pool))

        self.assertEqual(bound_state, "bound")
        self.assertEqual(bound["thred"]["name"], "worker")
        self.assertNotIn("thread", bound)
        self.assertEqual(released["state"], "released")
        self.assertEqual(len(pool.released), 1)

    def test_user_controls_runtime_service_name_and_lifecycle(self) -> None:
        scoped = self.lip.bind("application")
        scoped.provide("lip_thred_runtime", self.lip_thred_runtime)

        self.assertIs(scoped.get("lip_thred_runtime"), self.lip_thred_runtime)

        scoped.unload("application")

        with self.assertRaises(LookupError):
            scoped.get("lip_thred_runtime")

    def test_full_unload_releases_file_loaded_modules(self) -> None:
        module = self.lip.module("kernel_thred_definition")
        module_name = module.__name__
        self.assertIs(sys.modules[module_name], module)

        self.lip.unload()

        self.assertNotIn(module_name, sys.modules)

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
                load_composition(composition, repo=ROOT)

        self.assertEqual(type(raised.exception).__name__, "LoadError")
        self.assertIn("cannot use socket for composition", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
