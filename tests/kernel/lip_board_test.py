# -*- coding: utf-8 -*-

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType

import yaml

from kernel.thred.plugin.exception import NoMatches
from kernel.thred.plugin.host.board import create_board
from kernel.thred.plugin.host.file_loader import FileModuleLoader
from kernel.thred.plugin.manager.driver import DriverManager


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
    "plugins/tools/external_tools/ci_tools/generate/plugin/"
    "host_sibling/lip_check.py",
    "lip_check_test_module",
)
allow_list_generate = load(
    "plugins/tools/external_tools/ci_tools/generate/plugin/list/"
    "allow_list/allow_list_generate.py",
    "allow_list_generate_test_module",
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
        with self.assertRaises(NoMatches):
            self.lip.get("exec_command", "missing-shell")

    def test_unknown_socket_raises_no_matches(self) -> None:
        with self.assertRaises(NoMatches):
            self.lip.get("missing-socket", "bash")

    def test_pwsh_is_a_named_plug_on_the_same_socket(self) -> None:
        plug = self.lip.get("exec_command", "pwsh")
        self.assertEqual(plug.PLUGIN_NAME, "pwsh")
        self.assertTrue(callable(plug.dispatch))

    def test_file_loader_distinguishes_same_name_at_different_paths(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            for filename, marker in (("first.py", "first"), ("second.py", "second")):
                (repo / filename).write_text(
                    "PLUGIN_NAME = 'demo'\n"
                    f"MARKER = {marker!r}\n"
                    "def dispatch(*args, **kwargs):\n"
                    "    return MARKER\n",
                    encoding="utf-8",
                )
            loader = FileModuleLoader(repo)
            first = loader.load(
                "socket:test", "demo", "first.py", required="dispatch"
            )
            second = loader.load(
                "socket:test", "demo", "second.py", required="dispatch"
            )
            module_names = (first.__name__, second.__name__)

            self.assertIsNot(first, second)
            self.assertEqual((first.MARKER, second.MARKER), ("first", "second"))
            self.assertNotEqual(*module_names)
            loader.close()

        self.assertTrue(all(name not in sys.modules for name in module_names))

    def test_driver_load_failure_restores_previous_module(self) -> None:
        module_name = "_thred_test_restore"
        previous = ModuleType(module_name)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.py"
            path.write_text("PLUGIN_NAME = 'wrong'\n", encoding="utf-8")
            sys.modules[module_name] = previous
            try:
                with self.assertRaises(ValueError):
                    DriverManager.from_file(
                        "test", "expected", path, module_name=module_name
                    )
                self.assertIs(sys.modules[module_name], previous)
            finally:
                sys.modules.pop(module_name, None)

    def test_allow_list_cards_have_identical_semantics(self) -> None:
        payloads = [
            allow_list_generate._payload(allow_list_generate.load(fmt))
            for fmt in ("json", "yaml", "toml", "md")
        ]

        self.assertTrue(all(payload == payloads[0] for payload in payloads[1:]))
        self.assertIn("kernel/thred/plugin", payloads[0]["paths"])

    def test_runtime_import_graph_is_acyclic(self) -> None:
        import ast

        package = ROOT / "kernel" / "thred" / "plugin"
        paths = [
            *sorted((package / "manager").glob("*.py")),
            *sorted((package / "host").glob("*.py")),
        ]
        modules = {
            ".".join(path.relative_to(ROOT).with_suffix("").parts): path
            for path in paths
        }
        graph: dict[str, set[str]] = {name: set() for name in modules}
        for name, path in modules.items():
            tree = ast.parse(path.read_text(encoding="utf-8"))
            current_package = name.split(".")[:-1]
            for node in ast.walk(tree):
                candidates: list[str] = []
                if isinstance(node, ast.Import):
                    candidates.extend(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom):
                    if node.level:
                        keep = len(current_package) - node.level + 1
                        base = current_package[:keep]
                        target = ".".join([*base, *(node.module or "").split(".")])
                    else:
                        target = node.module or ""
                    candidates.append(target.rstrip("."))
                    candidates.extend(
                        f"{target.rstrip('.')}.{alias.name}"
                        for alias in node.names
                    )
                graph[name].update(
                    candidate for candidate in candidates if candidate in modules
                )

        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(name: str) -> None:
            if name in visiting:
                self.fail(f"runtime import cycle includes {name}")
            if name in visited:
                return
            visiting.add(name)
            for dependency in graph[name]:
                visit(dependency)
            visiting.remove(name)
            visited.add(name)

        for name in graph:
            visit(name)

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

    def test_lip_check_rejects_socket_as_composer_source(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            composition = repo / lip_check.COMPOSITION_PATH
            composition.parent.mkdir(parents=True)
            composition.write_text(
                "sockets: {}\n"
                "plugins:\n"
                "  - name: legacy\n"
                "    socket: exec_command\n",
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
            context["violations"][0]["rule"],
            "lip.composer.source",
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
