"""Forward a process request to the capability package it already loaded.

The process calls ``create_adapter()`` with no arguments. This module then
calls ``load`` on that package. Card files, message shape, tool arguments,
and compression functions stay in their own packages.
"""

from __future__ import annotations

import asyncio
import gc
import inspect
import sys
import types
from pathlib import Path
from typing import Any


_CAPABILITY_ROOT = Path(__file__).resolve().parent
_SELF_PATH = Path(__file__).resolve()
_LOAD = "load"


class ProcessAdapter:
    """One process-wide forwarder. It does not interpret provider cards."""

    sync_thread_safe = False

    def __init__(self, modules: list[Any]) -> None:
        self._modules = modules
        self._settings: dict[str, Any] = {}
        self._resource_params: dict[str, dict[str, Any]] = {}
        self._room: Any = None
        self._loader = _find_load(modules)
        self._async_loader = _find_async_load(modules)

    @property
    def is_async(self) -> bool:
        """Whether the loaded capability exposes an async loader."""
        return self._async_loader is not None

    def initialize(self, resource_context: Any, room: Any = None) -> None:
        self._settings = _settings(resource_context)
        self._resource_params = _resource_params(resource_context)
        self._room = room
        if room is not None:
            from kernel.environment import bind_room

            bind_room(room)

    def handle(self, request: dict[str, Any]) -> Any:
        operation = request.get("operation")
        if operation != _LOAD:
            raise ValueError(f"A capability process only accepts load, got {operation!r}")
        kind = request.get("kind")
        if not isinstance(kind, str) or not kind:
            raise ValueError("load must include a resource kind")
        loader = self._loader
        if loader is None:
            raise LookupError("This process has no load")
        return loader(kind, request.get("body"), self._params_for(kind))

    async def handle_async(self, request: dict[str, Any]) -> Any:
        """Handle an async loader directly or bridge a legacy sync loader."""
        loader = self._async_loader
        if loader is None:
            return self.handle(request)
        operation = request.get("operation")
        if operation != _LOAD:
            raise ValueError(f"A capability process only accepts load, got {operation!r}")
        kind = request.get("kind")
        if not isinstance(kind, str) or not kind:
            raise ValueError("load must include a resource kind")
        result = loader(kind, request.get("body"), self._params_for(kind))
        return await result if inspect.isawaitable(result) else result

    def _params_for(self, kind: str) -> dict[str, Any]:
        """Keep each resource kind's parameters with that kind.

        A tool plugin only receives parameters declared on its tool resource.
        Sandbox mode and scope stay in the process room, so a new sandbox
        parameter cannot leak into a tool function signature.
        """

        if kind == "tool":
            return dict(self._resource_params.get("tool") or {})
        params = dict(self._settings)
        params.update(self._resource_params.get(kind) or {})
        return params

    def shutdown(self) -> None:
        if self._room is not None:
            from kernel.environment import bind_room

            bind_room(None)
            self._room = None


def create_adapter(modules: list[Any] | None = None) -> ProcessAdapter:
    """Build the forwarder from the modules this process just loaded."""
    chosen = list(modules) if modules is not None else _loaded_plugin_modules()
    return ProcessAdapter(chosen)


def _settings(resource_context: Any) -> dict[str, Any]:
    raw = getattr(resource_context, "settings", None) or {}
    params = dict(raw) if isinstance(raw, dict) else {}
    declared_model = params.pop("id", None)
    params.pop("provider", None)
    if declared_model and "model" not in params:
        params["model"] = declared_model
    return params


def _resource_params(resource_context: Any) -> dict[str, dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for grant in getattr(resource_context, "grants", ()) or ():
        incoming = getattr(grant, "call_params", None) or {}
        if not isinstance(incoming, dict):
            continue
        kind = _kind_name(getattr(grant, "kind", ""))
        if not kind:
            continue
        grouped.setdefault(kind, {}).update(incoming)
    return grouped


def _kind_name(kind: object) -> str:
    return str(getattr(kind, "value", kind) or "")


def _find_load(modules: list[Any]) -> Any | None:
    for module in modules:
        loader = getattr(module, "load", None)
        if inspect.isfunction(loader):
            return loader
    return None


def _find_async_load(modules: list[Any]) -> Any | None:
    for module in modules:
        loader = getattr(module, "load_async", None)
        if inspect.iscoroutinefunction(loader):
            return loader
    return None


def _loaded_plugin_modules() -> list[Any]:
    """Find capability modules the process already loaded.

    The process loads plugin files without registering them in ``sys.modules``.
    Their module objects are still alive, and the file path is enough to tell
    them apart from this adapter.
    """
    gc.collect()
    found: list[Any] = []
    seen: set[str] = set()
    for module in (*sys.modules.values(), *gc.get_objects()):
        if not isinstance(module, types.ModuleType):
            continue
        path = _module_path(module)
        if path is None or path in seen:
            continue
        seen.add(path)
        found.append(module)
    found.sort(key=lambda module: _module_path(module) or "")
    return found


def _module_path(module: Any) -> str | None:
    raw = getattr(module, "__file__", None)
    if not raw:
        return None
    path = Path(raw).resolve()
    if path == _SELF_PATH:
        return None
    if path.name.startswith("test_"):
        return None
    if "tests" in path.parts:
        return None
    try:
        path.relative_to(_CAPABILITY_ROOT)
    except ValueError:
        return None
    name = getattr(module, "__name__", "")
    if name.startswith("capability."):
        return None
    return str(path)
