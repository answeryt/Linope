"""Load raw leaf capabilities without applying a composition contract."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ..exception import NoMatches
from .file_loader import FileModuleLoader


class ModuleLoader:
    """Resolve raw leaf modules by their configured ``PLUGIN_NAME``."""

    def __init__(
        self,
        modules: Mapping[str, str],
        files: FileModuleLoader,
    ) -> None:
        self._modules = modules
        self._files = files

    def get(self, name: str) -> Any:
        if name not in self._modules:
            raise NoMatches(f"no capability module named {name!r}")
        return self._files.load(
            "module",
            name,
            self._modules[name],
            required=None,
        )
