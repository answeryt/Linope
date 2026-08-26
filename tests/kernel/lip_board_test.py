# -*- coding: utf-8 -*-

from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path
from types import ModuleType


ROOT = Path(__file__).resolve().parents[2]
ALLOW_CARD = (
    ROOT
    / "tools"
    / "external_tools"
    / "ci_tools"
    / "generate"
    / "plugin"
    / "list"
    / "allow_list"
    / "allow_list_card"
    / "list.json"
)


def load(relative: str, module_name: str) -> ModuleType:
    path = ROOT / relative
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


board = load("kernel/thred/plugin/manager/lip/board.py", "lip_board_test_module")
lip_check = load(
    "tools/external_tools/ci_tools/generate/plugin/host_sibling/lip_check.py",
    "lip_check_test_module",
)


class LipBoardTest(unittest.TestCase):
    def setUp(self) -> None:
        sockets = json.loads(ALLOW_CARD.read_text(encoding="utf-8"))["sockets"]
        self.lip = board.Lip(sockets, repo=ROOT)

    def test_get_bash_by_name_without_importing_the_plug(self) -> None:
        plug = self.lip.get("exec_command", "bash")
        self.assertEqual(plug.PLUGIN_NAME, "bash")
        self.assertTrue(callable(plug.dispatch))
        payload = json.loads(
            plug.dispatch("bash", {"command": "", "description": "empty"})
        )
        self.assertFalse(payload["success"])
        self.assertIn("invalid command", payload["error"])

    def test_unknown_plug_raises_no_matches(self) -> None:
        with self.assertRaises(Exception) as ctx:
            self.lip.get("exec_command", "missing-shell")
        self.assertEqual(type(ctx.exception).__name__, "NoMatches")

    def test_unknown_socket_raises_no_matches(self) -> None:
        with self.assertRaises(Exception) as ctx:
            self.lip.get("missing-socket", "bash")
        self.assertEqual(type(ctx.exception).__name__, "NoMatches")

    def test_pwsh_is_a_named_plug_on_the_same_socket(self) -> None:
        plug = self.lip.get("exec_command", "pwsh")
        self.assertEqual(plug.PLUGIN_NAME, "pwsh")
        self.assertTrue(callable(plug.dispatch))

    def test_lip_check_accepts_the_allow_list_sockets(self) -> None:
        context = {
            "repo_root": str(ROOT),
            "allow_list": json.loads(ALLOW_CARD.read_text(encoding="utf-8")),
            "families": [
                {
                    "id": "lip",
                    "root": "kernel/thred/plugin/manager/lip",
                    "files": ["board.py"],
                }
            ],
            "allowed_families": [],
            "violations": [],
        }
        lip_check.run(context)
        self.assertEqual(context["violations"], [])

    def test_host_board_source_does_not_import_stevedore(self) -> None:
        import ast

        tree = ast.parse(
            (ROOT / "kernel/thred/plugin/manager/lip/board.py").read_text(
                encoding="utf-8"
            )
        )
        names: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names.extend(alias.name for alias in node.names if alias.name)
            elif isinstance(node, ast.ImportFrom) and node.module:
                names.append(node.module)
        self.assertFalse(
            any(name.split(".", 1)[0] in {"stevedore", "pluggy"} for name in names)
        )


if __name__ == "__main__":
    unittest.main()
