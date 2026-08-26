"""Assemble leaf plugins from ``composition.yaml``."""

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
    entries = data.get("plugins", [])
    if not isinstance(sockets, dict):
        raise LoadError("composition sockets must be a mapping")
    if not isinstance(entries, list):
        raise LoadError("composition plugins must be a list")

    root = Path(repo) if repo is not None else _DEFAULT_REPO
    lip = Context(sockets, repo=root)
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
                    or dependency in lip._runtime.services
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
        socket = entry.get("socket")
        if not isinstance(name, str) or not name:
            raise LoadError("each plugin needs a non-empty name")
        if name in names:
            raise LoadError(f"duplicate plugin name: {name!r}")
        if not isinstance(socket, str) or not socket:
            raise LoadError(f"plugin {name!r} needs a non-empty socket")
        try:
            module = lip.get(socket, name)
            validate(module, name)
        except (LookupError, ImportError, ProtocolError) as error:
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
    services = set(lip._runtime.services)
    for name, _module, inject, _config in pending:
        missing = [
            dependency
            for dependency in inject
            if dependency not in applied
            and dependency not in services
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
