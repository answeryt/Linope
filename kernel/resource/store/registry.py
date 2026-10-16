"""Register and open ledger implementations.

Built-in factories are installed by ``kernel.process.ledger``. This module
does not import ``kernel.process``.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol

from kernel.resource.store.locator import local_path, normalize_locator


class StoreFactory(Protocol):
    def __call__(self, locator: str, *, reap: bool = True) -> Any:
        ...


_registry: dict[str, StoreFactory] = {}
_BUILTINS = frozenset({"file", "memory"})
_ALIASES = {"local": "file"}
_DATABASE = "database"


def register_store(
    name: str,
    factory: StoreFactory,
    *,
    builtin: bool = False,
) -> None:
    if not name or name.strip() != name:
        raise ValueError("存储名称不能为空")
    if name in _BUILTINS and not builtin:
        raise ValueError("内置存储不能覆盖")
    _registry[name] = factory


def unregister_store(name: str) -> None:
    if name in _BUILTINS:
        raise ValueError("内置存储不能取消登记")
    _registry.pop(name, None)


def store_names() -> tuple[str, ...]:
    return tuple(sorted(_registry))


def open_store(
    locator: str | Path | Any | None = None,
    *,
    reap: bool = True,
):
    if locator is not None and not isinstance(locator, (str, Path)):
        return locator
    normalized = normalize_locator(locator)
    scheme = _scheme_for(normalized)
    factory = _registry.get(scheme)
    if factory is None and "://" in normalized:
        factory = _registry.get(_DATABASE)
    if factory is None:
        known = ", ".join(store_names())
        raise KeyError(f"未知存储 {normalized!r}。已知: {known}")
    return factory(normalized, reap=reap)


def backend_for(locator: str | Path) -> str:
    normalized = normalize_locator(locator)
    return _scheme_for(normalized)


def local_path_for(locator: str) -> Path:
    return local_path(locator)


def _scheme_for(locator: str) -> str:
    raw = locator.split(":", 1)[0].lower()
    return _ALIASES.get(raw, raw)
