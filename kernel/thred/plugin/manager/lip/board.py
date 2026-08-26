# -*- coding: utf-8 -*-
"""Host loader for the file-driver socket board.

Loads the in-tree stevedore ``lip`` extension by file path. This file
must not import ``stevedore``; leaf plugins must not import this file.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType


_PACKAGE_DIR = (
    Path(__file__).resolve().parent.parent / "stevedore" / "stevedore"
)


def _exec_module(name: str, path: Path, search: list[str]) -> ModuleType:
    existing = sys.modules.get(name)
    if existing is not None:
        return existing
    spec = importlib.util.spec_from_file_location(
        name,
        path,
        submodule_search_locations=search,
    )
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _load_lip() -> ModuleType:
    search = [str(_PACKAGE_DIR)]
    _exec_module("stevedore", _PACKAGE_DIR / "__init__.py", search)
    return _exec_module("stevedore.lip", _PACKAGE_DIR / "lip.py", search)


Lip = _load_lip().Lip
