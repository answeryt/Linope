"""Repository-bound file loading for capability modules."""

from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path
from typing import Any

_MISSING_MODULE = object()


class DriverManager:
    def __init__(self, *, namespace: str, name: str, module: Any) -> None:
        self.namespace = namespace
        self.name = name
        self._module = module

    @property
    def driver(self) -> Any:
        return self._module

    @classmethod
    def from_file(
        cls,
        namespace: str,
        name: str,
        path: str | Path,
        *,
        module_name: str | None = None,
        required: str | None = "dispatch",
        match_plugin_name: bool | None = None,
    ) -> "DriverManager":
        file_path = Path(path).resolve()
        if not file_path.is_file():
            raise ImportError(file_path)

        spec_name = module_name or f"_compose_{namespace}_{name}".replace(".", "_")
        spec = importlib.util.spec_from_file_location(spec_name, file_path)
        if spec is None or spec.loader is None:
            raise ImportError(file_path)

        module = importlib.util.module_from_spec(spec)
        previous = sys.modules.get(spec_name)
        sys.modules[spec_name] = module
        try:
            spec.loader.exec_module(module)
        except BaseException:
            # Restore sys.modules exactly to the previous state.
            if previous is None:
                sys.modules.pop(spec_name, None)
            else:
                sys.modules[spec_name] = previous
            raise

        actual_name = getattr(module, "PLUGIN_NAME", None)
        # Recipe graph nodes may share one host module. The artifact name is the
        # node identity; PLUGIN_NAME names the host file, not each card/recipe.
        should_match = match_plugin_name
        if should_match is None:
            should_match = namespace != "recipe"
        if should_match and actual_name != name:
            if previous is None:
                sys.modules.pop(spec_name, None)
            else:
                sys.modules[spec_name] = previous
            raise ValueError(
                f"PLUGIN_NAME must be {name!r}, got {actual_name!r}"
            )

        if required is not None and not callable(getattr(module, required, None)):
            if previous is None:
                sys.modules.pop(spec_name, None)
            else:
                sys.modules[spec_name] = previous
            raise TypeError(
                f"plugin {name!r} must provide callable {required!r}"
            )

        return cls(namespace=namespace, name=name, module=module)


class FileModuleLoader:
    """Load and cache named modules without assuming their business API."""

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
            raise ImportError(
                f"capability path escapes repository: {raw_path}"
            ) from error

        key = (namespace, name, path, required)
        if key in self._cache:
            return self._cache[key]

        prefix = "_compose_" + "".join(
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
