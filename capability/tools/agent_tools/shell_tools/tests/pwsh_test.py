# -*- coding: utf-8 -*-
"""plugin-unit sample: load the pwsh leaf by file."""

from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path


def _load():
    path = Path(__file__).resolve().parents[1] / "pwsh_plugin.py"
    spec = importlib.util.spec_from_file_location("pwsh_plugin_leaf", path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PwshPluginTest(unittest.TestCase):
    def setUp(self) -> None:
        self.pwsh = _load()

    def test_leaf_identity_and_tool_contract(self) -> None:
        self.assertEqual(self.pwsh.PLUGIN_NAME, "pwsh")
        schemas = self.pwsh.tool_schemas()
        self.assertEqual(schemas[0]["name"], "pwsh")
        self.assertEqual(schemas[0]["parameters"]["required"], ["command", "description"])

    def test_dispatch_rejects_unknown_tool(self) -> None:
        payload = json.loads(self.pwsh.dispatch("bash", {"command": "Get-Location"}))
        self.assertFalse(payload["success"])
        self.assertIn("unknown tool", payload["error"])

    def test_rejects_empty_command(self) -> None:
        payload = json.loads(self.pwsh.dispatch("pwsh", {"command": "  ", "description": "noop"}))
        self.assertFalse(payload["success"])
        self.assertIn("invalid command", payload["error"])

    def test_runs_write_output_when_powershell_exists(self) -> None:
        if self.pwsh._powershell() is None:
            self.skipTest("powershell is not installed")
        import os

        from kernel.environment import (
            HostExecutionPolicy,
            KernelEnvironment,
            ProcessEnvironment,
            using_room,
        )

        shell = ProcessEnvironment.current(pid=os.getpid(), capability_id="tools.pwsh")
        room = KernelEnvironment.build(
            shell=shell,
            policy=HostExecutionPolicy(),
            max_concurrent_tasks=1,
            max_sync_workers=1,
            access_mode="danger-full-access",
            confine=False,
        )
        with using_room(room):
            payload = json.loads(
                self.pwsh.dispatch(
                    "pwsh",
                    {"command": "Write-Output hello-from-pwsh", "description": "Print a marker"},
                )
            )
        self.assertTrue(payload["success"], payload)
        self.assertEqual(payload["exitCode"], 0)
        self.assertIn("hello-from-pwsh", payload["text"])


if __name__ == "__main__":
    unittest.main()
