"""Load the modified stevedore socket board without a static vendor import."""

from __future__ import annotations

import importlib.util
from collections.abc import Mapping
from pathlib import Path
import sys
from typing import Any


class NoMatches(LookupError):
    """No contract-compliant plug exists for a socket and name."""


class Board:
    """Translate vendor lookup errors while delegating lookup to stevedore."""

    def __init__(self, vendor_lip: Any, vendor_no_matches: type[Exception]) -> None:
        self._vendor_lip = vendor_lip
        self._vendor_no_matches = vendor_no_matches

    def get(self, socket: str, name: str) -> Any:
        try:
            return self._vendor_lip.get(socket, name)
        except self._vendor_no_matches as error:
            raise NoMatches(str(error)) from error


def create_board(
    sockets: Mapping[str, Mapping[str, str]], *, repo: Path
) -> Any:
    package = _load_package(
        "_thred_vendor_stevedore",
        Path(__file__).resolve().parent.parent
        / "vendor"
        / "stevedore"
        / "src"
        / "stevedore",
    )
    lip_module = _load_submodule(package.__name__, "lip")
    exception_module = _load_submodule(package.__name__, "exception")
    return Board(
        lip_module.Lip(sockets, repo=repo),
        exception_module.NoMatches,
    )


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


def _load_submodule(package: str, name: str) -> Any:
    qualified = f"{package}.{name}"
    existing = sys.modules.get(qualified)
    if existing is not None:
        return existing
    parent = sys.modules[package]
    path = Path(parent.__file__).resolve().parent / f"{name}.py"
    spec = importlib.util.spec_from_file_location(qualified, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[qualified] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(qualified, None)
        raise
    return module
