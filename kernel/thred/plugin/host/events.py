"""Load the modified pluggy event engine without a static vendor import."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
from typing import Any


def create_event_manager() -> Any:
    package = _load_package(
        "_thred_vendor_pluggy",
        Path(__file__).resolve().parent.parent
        / "vendor"
        / "pluggy"
        / "src"
        / "pluggy",
    )
    return package.PluginManager("kernel_thred")


def _load_package(name: str, directory: Path) -> Any:
    existing = sys.modules.get(name)
    if existing is not None:
        return existing
    spec = importlib.util.spec_from_file_location(
        name,
        directory / "__init__.py",
        submodule_search_locations=[str(directory)],
    )
    if spec is None or spec.loader is None:
        raise ImportError(directory)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(name, None)
        raise
    return module
