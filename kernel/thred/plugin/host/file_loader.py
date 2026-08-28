"""Shared repository-bound file loading for Host policies."""

from __future__ import annotations

import hashlib
from pathlib import Path
import sys
from typing import Any

from ..manager.driver import DriverManager


_MISSING_MODULE = object()


class FileModuleLoader:
    """Load and cache named modules without deciding how they are used."""

    def __init__(self, repo: Path) -> None:
        self._repo = repo.resolve()
        self._cache: dict[tuple[str, str, Path, str | None], Any] = {}
        self._loaded: dict[str, tuple[Any, Any]] = {}

    def load(
        self,
        namespace: str,
        name: str,
        raw_path: str,
        *,
        required: str | None,
    ) -> Any:
        path = (self._repo / raw_path).resolve()
        try:
            path.relative_to(self._repo)
        except ValueError as error:
            raise ImportError(f"plugin path escapes repository: {raw_path}") from error
        key = (namespace, name, path, required)
        if key in self._cache:
            return self._cache[key]
        prefix = "_thred_" + "".join(
            character if character.isalnum() else "_"
            for character in f"{namespace}_{name}"
        )
        identity = f"{namespace}\0{name}\0{path}\0{required}"
        digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16]
        module_name = f"{prefix}_{digest}"
        previous = sys.modules.get(module_name, _MISSING_MODULE)
        manager = DriverManager.from_file(
            namespace,
            name,
            path,
            module_name=module_name,
            required=required,
        )
        module = manager.driver
        self._cache[key] = module
        self._loaded[module_name] = (module, previous)
        return module

    def close(self) -> None:
        """Remove only module registrations created by this loader."""
        for module_name, (module, previous) in reversed(self._loaded.items()):
            if sys.modules.get(module_name) is not module:
                continue
            if previous is _MISSING_MODULE:
                sys.modules.pop(module_name, None)
            else:
                sys.modules[module_name] = previous
        self._loaded.clear()
        self._cache.clear()
