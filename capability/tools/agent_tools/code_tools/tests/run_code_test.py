# -*- coding: utf-8 -*-
"""plugin-unit sample: load the run_code leaf by file."""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


def _load():
    path = Path(__file__).resolve().parents[1] / "run_code_plugin.py"
    spec = importlib.util.spec_from_file_location("run_code_plugin_leaf", path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RunCodePluginTest(unittest.TestCase):
    def setUp(self) -> None:
        self.run_code = _load()

    def test_leaf_identity_and_tool_contract(self) -> None:
        self.assertEqual(self.run_code.PLUGIN_NAME, "run_code")
        schemas = self.run_code.tool_schemas()
        self.assertEqual(schemas[0]["name"], "run_code")
        self.assertEqual(schemas[0]["parameters"]["required"], ["code", "description"])

    def test_returns_print_and_value(self) -> None:
        payload = json.loads(
            self.run_code.dispatch(
                "run_code",
                {
                    "code": "print('seen')\nreturn {'n': 1 + 1}",
                    "description": "Add one and one",
                },
            )
        )
        self.assertTrue(payload["success"], payload)
        self.assertEqual(payload["logs"], ["seen"])
        self.assertEqual(payload["result"], {"n": 2})

    def test_calls_read_tool(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "notes.txt").write_text("alpha\n", encoding="utf-8")
            payload = json.loads(
                self.run_code.dispatch(
                    "run_code",
                    {
                        "code": "return tools.read({'file_path': 'notes.txt'})['content']",
                        "description": "Read notes through tools",
                    },
                    workspace=directory,
                )
            )
        self.assertTrue(payload["success"], payload)
        self.assertIn("alpha", payload["result"])

    def test_write_follows_the_bound_room(self) -> None:
        import os

        from kernel.environment import (
            HostExecutionPolicy,
            KernelEnvironment,
            ProcessEnvironment,
            using_room,
        )

        with tempfile.TemporaryDirectory() as directory:
            shell = ProcessEnvironment.current(
                pid=os.getpid(),
                capability_id="tools.run_code",
                cwd=directory,
            )
            readonly = KernelEnvironment.build(
                shell=shell,
                policy=HostExecutionPolicy(),
                max_concurrent_tasks=1,
                max_sync_workers=1,
                access_mode="read-only",
                confine=False,
            )
            code = "return tools.write({'file_path': 'made.txt', 'content': 'hello'})"
            with using_room(readonly):
                denied = json.loads(
                    self.run_code.dispatch(
                        "run_code",
                        {"code": code, "description": "Try to write a file"},
                        workspace=directory,
                    )
                )
            self.assertTrue(denied["success"], denied)
            self.assertFalse(denied["result"]["success"])
            self.assertFalse((Path(directory) / "made.txt").exists())

            writable = KernelEnvironment.build(
                shell=shell,
                policy=HostExecutionPolicy(),
                max_concurrent_tasks=1,
                max_sync_workers=1,
                access_mode="workspace-write",
                confine=False,
            )
            with using_room(writable):
                allowed = json.loads(
                    self.run_code.dispatch(
                        "run_code",
                        {"code": code, "description": "Write a file"},
                        workspace=directory,
                    )
                )
            self.assertTrue(allowed["success"], allowed)
            self.assertEqual((Path(directory) / "made.txt").read_text(encoding="utf-8"), "hello")

    def test_rejects_calling_itself(self) -> None:
        payload = json.loads(
            self.run_code.dispatch(
                "run_code",
                {
                    "code": "return tools.run_code({'code': 'return 1', 'description': 'again'})",
                    "description": "Recurse into run_code",
                },
            )
        )
        self.assertFalse(payload["success"])
        self.assertIn("cannot call itself", payload["error"])


if __name__ == "__main__":
    unittest.main()
