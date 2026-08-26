# -*- coding: utf-8 -*-

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from types import ModuleType

import yaml

from kernel.thred.plugin.host.board import create_board


ROOT = Path(__file__).resolve().parents[2]
COMPOSITION = ROOT / "kernel" / "thred" / "plugin" / "composition.yaml"


def load(relative: str, module_name: str) -> ModuleType:
    path = ROOT / relative
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


lip_check = load(
    "tools/external_tools/ci_tools/generate/plugin/host_sibling/lip_check.py",
    "lip_check_test_module",
)


class LipBoardTest(unittest.TestCase):
    def setUp(self) -> None:
        composition = yaml.safe_load(COMPOSITION.read_text(encoding="utf-8"))
        self.lip = create_board(composition["sockets"], repo=ROOT)

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

    def test_lip_check_accepts_the_host_composition_sockets(self) -> None:
        context = {
            "repo_root": str(ROOT),
            "allow_list": {},
            "families": [
                {
                    "id": "host",
                    "root": "kernel/thred/plugin/host",
                    "files": ["board.py", "loader.py"],
                },
                {
                    "id": "tests",
                    "root": "kernel/thred/plugin/tests",
                    "files": ["test_context.py"],
                },
            ],
            "allowed_families": [],
            "violations": [],
        }
        lip_check.run(context)
        self.assertEqual(context["violations"], [])

    def test_lip_check_accepts_composition_without_sockets(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            composition = repo / lip_check.COMPOSITION_PATH
            composition.parent.mkdir(parents=True)
            composition.write_text("plugins: []\n", encoding="utf-8")
            context = {
                "repo_root": str(repo),
                "families": [],
                "allowed_families": [],
                "violations": [],
            }

            lip_check.run(context)

        self.assertEqual(context["violations"], [])

    def test_lip_check_reports_composition_for_invalid_socket_mapping(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            composition = repo / lip_check.COMPOSITION_PATH
            composition.parent.mkdir(parents=True)
            composition.write_text(
                "sockets:\n  exec_command: []\nplugins: []\n",
                encoding="utf-8",
            )
            context = {
                "repo_root": str(repo),
                "families": [],
                "allowed_families": [],
                "violations": [],
            }

            lip_check.run(context)

        self.assertEqual(len(context["violations"]), 1)
        self.assertEqual(
            context["violations"][0]["path"],
            lip_check.COMPOSITION_PATH,
        )

    def test_host_board_source_does_not_import_stevedore(self) -> None:
        import ast

        tree = ast.parse(
            (ROOT / "kernel/thred/plugin/host/board.py").read_text(
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
