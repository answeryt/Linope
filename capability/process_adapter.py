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
        self._call_params: dict[str, Any] = {}
        self._room: Any = None
        self._loader = _find_load(modules)
        self._async_loader = _find_async_load(modules)

    @property
    def is_async(self) -> bool:
        """Whether the loaded capability exposes an async loader."""
        return self._async_loader is not None

    def initialize(self, resource_context: Any, room: Any = None) -> None:
        params: dict[str, Any] = {}
        for grant in getattr(resource_context, "grants", ()) or ():
            incoming = getattr(grant, "call_params", None) or {}
            params.update(incoming)
        self._call_params = params
        self._room = room
        if room is not None:
            from kernel.environment import bind_room

            bind_room(room)

    def handle(self, request: dict[str, Any]) -> Any:
        operation = request.get("operation")
        if operation != _LOAD:
            raise ValueError(f"能力进程只接受 load，收到 {operation!r}")
        kind = request.get("kind")
        if not isinstance(kind, str) or not kind:
            raise ValueError("load 必须带上资源种类")
        loader = self._loader
        if loader is None:
            raise LookupError("这个进程没有 load")
        return loader(kind, request.get("body"), self._call_params)

    async def handle_async(self, request: dict[str, Any]) -> Any:
        """Handle an async loader directly or bridge a legacy sync loader."""
        loader = self._async_loader
        if loader is None:
            return self.handle(request)
        operation = request.get("operation")
        if operation != _LOAD:
            raise ValueError(f"能力进程只接受 load，收到 {operation!r}")
        kind = request.get("kind")
        if not isinstance(kind, str) or not kind:
            raise ValueError("load 必须带上资源种类")
        result = loader(kind, request.get("body"), self._call_params)
        return await result if inspect.isawaitable(result) else result

    def shutdown(self) -> None:
        if self._room is not None:
            from kernel.environment import bind_room

            bind_room(None)
            self._room = None


def create_adapter() -> ProcessAdapter:
    """Build the forwarder from capability modules already imported here."""
    return ProcessAdapter(_loaded_plugin_modules())


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
