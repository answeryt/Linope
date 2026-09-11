# -*- coding: utf-8 -*-

from __future__ import annotations

import importlib.util
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
    / "surface_check.py"
)


def load(path: Path, module_name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


surface_check = load(CHECK_PATH, "surface_check_test_module")


def _context(repo: Path, families: list[dict]) -> dict:
    return {"repo_root": str(repo), "families": families, "violations": []}


def _rules(context: dict) -> list[str]:
    return [str(item.get("rule")) for item in context.get("violations") or []]


class SurfaceCheckTest(unittest.TestCase):
    def test_accepts_named_apply_helpers(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            family = repo / "params"
            family.mkdir()
            (family / "sampling_params.py").write_text(
                "def apply_temperature(request_kwargs, parameters):\n    return None\n",
                encoding="utf-8",
            )
            context = _context(
                repo,
                [{"id": "params", "root": "params", "files": ["sampling_params.py"]}],
            )
            surface_check.run(context)
        self.assertNotIn("surface.entry_point", _rules(context))

    def test_rejects_apply_family_without_apply_function(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            family = repo / "params"
            family.mkdir()
            (family / "sampling_params.py").write_text(
                "def apply_temperature(request_kwargs, parameters):\n    return None\n",
                encoding="utf-8",
            )
            (family / "other.py").write_text("def helper():\n    return None\n", encoding="utf-8")
            context = _context(
                repo,
                [
                    {
                        "id": "params",
                        "root": "params",
                        "files": ["sampling_params.py", "other.py"],
                    }
                ],
            )
            surface_check.run(context)
        self.assertIn("surface.entry_point", _rules(context))


if __name__ == "__main__":
    unittest.main()
