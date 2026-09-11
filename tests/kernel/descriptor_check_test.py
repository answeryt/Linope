# -*- coding: utf-8 -*-

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from types import ModuleType


ROOT = Path(__file__).resolve().parents[2]
CHECK_PATH = (
    ROOT
    / "capability"
    / "tools"
    / "external_tools"
    / "ci_tools"
    / "generate"
    / "plugin"
    / "host_sibling"
    / "descriptor_check.py"
)


def load(path: Path, module_name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


descriptor_check = load(CHECK_PATH, "descriptor_check_test_module")


def _context(repo: Path) -> dict:
    return {"repo_root": str(repo), "violations": []}


def _rules(context: dict) -> list[str]:
    return [str(item.get("rule")) for item in context.get("violations") or []]


class DescriptorCheckTest(unittest.TestCase):
    def test_accepts_model_cluster_leaf_and_card(self) -> None:
        context = _context(ROOT)
        descriptor_check.run(context)
        paths = {
            str(item.get("path"))
            for item in context["violations"]
            if str(item.get("path", "")).replace("\\", "/").endswith(
                ("assemble.py", "plugin.json")
            )
        }
        self.assertEqual(paths, set())

    def test_rejects_install_word_kind(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            leaf = repo / "leaf.py"
            leaf.write_text(
                "MODEL_CAPABILITY = {\n"
                "    'name': 'model.thread',\n"
                "    'kind': 'recipe',\n"
                "    'provides': ['model.thread'],\n"
                "    'requires': [],\n"
                "}\n",
                encoding="utf-8",
            )
            context = _context(repo)
            descriptor_check.run(context)
        self.assertIn("descriptor.kind.install_word", _rules(context))

    def test_rejects_missing_requirement_capability(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            (repo / "leaf.py").write_text(
                "CAPABILITY = {\n"
                "    'name': 'context.compression.window',\n"
                "    'kind': 'context.compression',\n"
                "    'provides': ['context.compression.window'],\n"
                "    'requires': [{'cardinality': 'many'}],\n"
                "}\n",
                encoding="utf-8",
            )
            context = _context(repo)
            descriptor_check.run(context)
        self.assertIn("descriptor.requires", _rules(context))

    def test_rejects_capability_contract_import(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            (repo / "leaf.py").write_text(
                "from capability.contract import model_thread\n"
                "MODEL_CAPABILITY = {\n"
                "    'name': 'model.thread',\n"
                "    'kind': 'model.thread',\n"
                "    'provides': ['model.thread'],\n"
                "    'requires': [],\n"
                "}\n",
                encoding="utf-8",
            )
            context = _context(repo)
            descriptor_check.run(context)
        self.assertIn("descriptor.contract_import", _rules(context))

    def test_rejects_missing_manifest_entry(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            host = repo / "host.py"
            host.write_text("def apply(ctx, config):\n    return None\n", encoding="utf-8")
            (repo / "plugin.json").write_text(
                json.dumps(
                    {
                        "name": "model.card.demo",
                        "kind": "model.card",
                        "provides": ["model.card"],
                        "source": "host.py",
                        "entry": "register_card",
                    }
                ),
                encoding="utf-8",
            )
            context = _context(repo)
            descriptor_check.run(context)
        self.assertIn("descriptor.entry", _rules(context))


if __name__ == "__main__":
    unittest.main()
