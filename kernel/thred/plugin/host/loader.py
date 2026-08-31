"""Apply path-selected composition Recipes from ``composition.yaml``."""

from __future__ import annotations

from pathlib import Path
from types import ModuleType
from typing import Any

from .assembler import Assembler
from .contracts import PluginState
from .lip import Context
from .protocol import (
    ProtocolError,
    inject_names,
    plugin_config,
    validate,
)
from .sources import source_from_mapping

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
    sources = data.get("sources", [])
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
    if not isinstance(sources, list):
        raise LoadError("composition sources must be a list")

    root = Path(repo) if repo is not None else _DEFAULT_REPO
    lip = Context(sockets, modules=modules, repo=root)
    assembler = Assembler(lip)
    loaded = _load_plugins(lip, entries)
    try:
        fibers = [
            lip.plugin(
                module,
                config,
                name=name,
                requirements=inject,
                source=str(getattr(module, "__file__", "")),
            )
            for name, module, inject, config in loaded
        ]
        pending = [
            fiber for fiber in fibers if fiber.state is PluginState.PENDING
        ]
        if pending:
            _raise_unsatisfied_fibers(pending, lip)
        for declaration in sources:
            if not isinstance(declaration, dict):
                raise LoadError("composition source entries must be mappings")
            try:
                source = source_from_mapping(declaration, base=root)
                assembler.mount_source(
                    source,
                    strict=bool(declaration.get("strict", False)),
                )
            except Exception as error:
                raise LoadError(f"cannot load plugin source: {error}") from error
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


def _raise_unsatisfied_fibers(pending: list[Any], lip: Context) -> None:
    pending_names = {fiber.name for fiber in pending}
    for fiber in pending:
        missing = [
            dependency
            for dependency in fiber.missing
            if dependency not in pending_names
        ]
        if missing:
            raise LoadError(
                f"plugin {fiber.name!r} injects missing {missing!r}"
            )
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
