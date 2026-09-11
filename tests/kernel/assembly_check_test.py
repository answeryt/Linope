# -*- coding: utf-8 -*-

from __future__ import annotations

import ast
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
    / "assembly_check.py"
)


def load(path: Path, module_name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


assembly_check = load(CHECK_PATH, "assembly_check_test_module")


def _context(repo: Path) -> dict:
    return {"repo_root": str(repo), "violations": []}


def _rules(context: dict) -> list[str]:
    return [str(item.get("rule")) for item in context.get("violations") or []]


COMPOSER_HEADER = (
    "from kernel.compose.capability import Capability\n"
    "from kernel.compose.capability import CapabilityCatalog\n"
    "from kernel.compose.capability import CapabilityGraphResolver\n"
    "from kernel.compose.capability import ComposeSpec\n"
    "from kernel.compose.capability import inject\n"
)


class AssemblyCheckTest(unittest.TestCase):
    def test_accepts_model_composer(self) -> None:
        context = _context(ROOT)
        assembly_check.run(context)
        composer_hits = [
            item
            for item in context["violations"]
            if str(item.get("path", "")).replace("\\", "/").endswith(
                "model/runtime/assemble.py"
            )
        ]
        self.assertEqual(composer_hits, [])

    def test_rejects_local_discover(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            (repo / "compose.py").write_text(
                COMPOSER_HEADER
                + "class LocalSource:\n"
                "    def discover(self):\n"
                "        return ()\n",
                encoding="utf-8",
            )
            context = _context(repo)
            assembly_check.run(context)
        self.assertIn("assembly.source.discover", _rules(context))

    def test_rejects_kind_translation_table(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            (repo / "compose.py").write_text(
                COMPOSER_HEADER
                + "_DOMAIN_KIND = {'model.interface': 'module'}\n",
                encoding="utf-8",
            )
            context = _context(repo)
            assembly_check.run(context)
        self.assertIn("assembly.kind.local_map", _rules(context))

    def test_rejects_capability_prefix_scan(self) -> None:
        source = (
            COMPOSER_HEADER
            + "def pick(ctx):\n"
            "    prefix = 'model.parameters.'\n"
            "    return [item.value for item in ctx.capabilities() "
            "if item.key.startswith(prefix)]\n"
        )
        tree = ast.parse(source)
        self.assertTrue(assembly_check._scans_capability_prefix(tree))
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            (repo / "compose.py").write_text(source, encoding="utf-8")
            context = _context(repo)
            assembly_check.run(context)
        self.assertIn("assembly.nodes.prefix", _rules(context))

    def test_rejects_wrapped_adapter_registration(self) -> None:
        source = (
            COMPOSER_HEADER
            + "from capability.model.runtime.assemble import FunctionModelAdapter\n"
            "class Wrapper:\n"
            "    def __init__(self, inner):\n"
            "        self.inner = inner\n"
            "    async def stream(self, request):\n"
            "        async for item in self.inner.stream(request):\n"
            "            yield item\n"
            "def wire(ctx, interface):\n"
            "    adapter = FunctionModelAdapter(interface.call_api, {})\n"
            "    ctx.get('llm').register_adapter(['demo'], Wrapper(adapter))\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            (repo / "compose.py").write_text(source, encoding="utf-8")
            context = _context(repo)
            assembly_check.run(context)
        self.assertIn("assembly.bridge.adapter", _rules(context))

    def test_accepts_cap_bus_function_adapter(self) -> None:
        source = (
            COMPOSER_HEADER
            + "from kernel.compose.capability import CapBus\n"
            "from capability.model.runtime.assemble import FunctionModelAdapter\n"
            "def wire(bus, interface):\n"
            "    adapter = FunctionModelAdapter(interface.call_api, {})\n"
            "    return bus.publish('openai', payload={'provider': 'openai'})\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            (repo / "compose.py").write_text(source, encoding="utf-8")
            context = _context(repo)
            assembly_check.run(context)
        rules = _rules(context)
        self.assertNotIn("assembly.bridge.adapter", rules)
        self.assertNotIn("assembly.bridge.adapter_source", rules)
        self.assertNotIn("assembly.bridge.kernel_services", rules)

    def test_rejects_kernel_services_import(self) -> None:
        source = (
            COMPOSER_HEADER
            + "from kernel.compose.capability.services import FunctionModelAdapter\n"
            "def wire():\n"
            "    return FunctionModelAdapter\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            (repo / "compose.py").write_text(source, encoding="utf-8")
            context = _context(repo)
            assembly_check.run(context)
        rules = _rules(context)
        self.assertIn("assembly.bridge.kernel_services", rules)
        self.assertIn("assembly.bridge.adapter_source", rules)

    def test_rejects_reflective_dynamic_dispatch(self) -> None:
        source = (
            COMPOSER_HEADER
            + "def wire(module):\n"
            "    for name, fn in vars(module).items():\n"
            "        if name.startswith('apply_') and callable(fn):\n"
            "            fn(request_kwargs={})\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            (repo / "compose.py").write_text(source, encoding="utf-8")
            context = _context(repo)
            assembly_check.run(context)
        self.assertIn("assembly.bind.dynamic_dispatch", _rules(context))


if __name__ == "__main__":
    unittest.main()
