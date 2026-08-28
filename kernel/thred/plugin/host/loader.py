"""Apply path-selected composition Recipes from ``composition.yaml``."""

from __future__ import annotations

from pathlib import Path
from types import ModuleType
from typing import Any

from .lip import Context
from .protocol import (
    ProtocolError,
    apply_function,
    inject_names,
    plugin_config,
    validate,
)

_PLUGIN_DIR = Path(__file__).resolve().parent.parent
_DEFAULT_COMPOSITION = _PLUGIN_DIR / "composition.yaml"
_DEFAULT_REPO = _PLUGIN_DIR.parents[2]
_UNSET = object()


class LoadError(RuntimeError):
    """The requested plugin composition cannot be assembled."""


def load_composition(
    path: str | Path | None = None,
    *,
    repo: str | Path | None = None,
) -> Context:
    data = _read_yaml(Path(path) if path is not None else _DEFAULT_COMPOSITION)
    sockets = data.get("sockets", {})
    modules = data.get("modules", {})
    entries = data.get("plugins", [])
    if not isinstance(sockets, dict):
        raise LoadError("composition sockets must be a mapping")
    if not isinstance(modules, dict):
        raise LoadError("composition modules must be a mapping")
    if any(
        not isinstance(name, str)
        or not name
        or not isinstance(module_path, str)
        or not module_path
        for name, module_path in modules.items()
    ):
        raise LoadError("composition modules must map names to non-empty paths")
    if not isinstance(entries, list):
        raise LoadError("composition plugins must be a list")

    root = Path(repo) if repo is not None else _DEFAULT_REPO
    lip = Context(sockets, modules=modules, repo=root)
    loaded = _load_plugins(lip, entries)
    pending = list(loaded)
    applied: set[str] = set()

    try:
        while pending:
            ready = [
                item
                for item in pending
                if all(
                    dependency in applied
                    or lip.has_service(dependency)
                    for dependency in item[2]
                )
            ]
            if not ready:
                _raise_unsatisfied(pending, applied, lip)
            for name, module, _inject, config in ready:
                scoped = lip.bind(name)
                cleanup = apply_function(module)(scoped, config)
                if cleanup is not None:
                    scoped.effect(cleanup)
                applied.add(name)
                pending.remove((name, module, _inject, config))
    except BaseException:
        lip.unload()
        raise
    return lip


def _load_plugins(
    lip: Context, entries: list[Any]
) -> list[tuple[str, ModuleType, tuple[str, ...], Any]]:
    loaded: list[tuple[str, ModuleType, tuple[str, ...], Any]] = []
    names: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise LoadError("each plugin entry must be a mapping")
        name = entry.get("name")
        path = entry.get("path")
        if not isinstance(name, str) or not name:
            raise LoadError("each plugin needs a non-empty name")
        if name in names:
            raise LoadError(f"duplicate plugin name: {name!r}")
        if "socket" in entry:
            raise LoadError(
                f"plugin {name!r} cannot use socket for composition; "
                "select tools in sockets and load Recipes by path"
            )
        if not isinstance(path, str) or not path:
            raise LoadError(f"plugin {name!r} needs a non-empty path")
        try:
            module = lip.load_recipe(name, path)
            validate(module, name)
        except (
            LookupError,
            ImportError,
            OSError,
            ProtocolError,
            TypeError,
            ValueError,
        ) as error:
            raise LoadError(f"cannot load plugin {name!r}: {error}") from error
        declared = entry.get("config", _UNSET)
        config = plugin_config(module) if declared is _UNSET else declared
        loaded.append((name, module, inject_names(module), config))
        names.add(name)
    return loaded


def _raise_unsatisfied(
    pending: list[tuple[str, ModuleType, tuple[str, ...], Any]],
    applied: set[str],
    lip: Context,
) -> None:
    pending_names = {name for name, _module, _inject, _config in pending}
    for name, _module, inject, _config in pending:
        missing = [
            dependency
            for dependency in inject
            if dependency not in applied
            and not lip.has_service(dependency)
            and dependency not in pending_names
        ]
        if missing:
            raise LoadError(f"plugin {name!r} injects missing {missing!r}")
    raise LoadError(f"plugin inject cycle: {sorted(pending_names)!r}")


def _read_yaml(path: Path) -> dict[str, Any]:
    try:
        import yaml
    except ImportError as error:
        raise LoadError("PyYAML is required to read composition.yaml") from error
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as error:
        raise LoadError(f"cannot read {path}: {error}") from error
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise LoadError("composition.yaml must contain a mapping")
    return data
