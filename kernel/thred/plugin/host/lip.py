"""Host facade over stevedore sockets, pluggy events, and unload effects."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from .board import create_board
from .events import create_event_manager
from .recipe_loader import RecipeLoader

Cleanup = Callable[[], Any]
_MISSING = object()


class NoService(LookupError):
    """No Host service has been provided under the requested name."""


class _Runtime:
    def __init__(
        self,
        sockets: Mapping[str, Mapping[str, str]],
        modules: Mapping[str, str],
        repo: Path,
    ) -> None:
        self.board = create_board(sockets, modules=modules, repo=repo)
        self.recipes = RecipeLoader(repo)
        self.events = create_event_manager()
        self.services: dict[str, Any] = {}
        self.effects: dict[str, list[Cleanup]] = defaultdict(list)
        self.order: list[str] = []


class Context:
    """The public ``lip`` object passed to ``apply(lip, config)``."""

    def __init__(
        self,
        sockets: Mapping[str, Mapping[str, str]] | None = None,
        *,
        modules: Mapping[str, str] | None = None,
        repo: str | Path | None = None,
        _runtime: _Runtime | None = None,
        _owner: str | None = None,
    ) -> None:
        root = Path(repo) if repo is not None else Path.cwd()
        self._runtime = _runtime or _Runtime(sockets or {}, modules or {}, root)
        self._owner = _owner

    def bind(self, plugin: str) -> "Context":
        if plugin not in self._runtime.order:
            self._runtime.order.append(plugin)
        return Context(_runtime=self._runtime, _owner=plugin)

    def provide(self, name: str, value: Any) -> None:
        previous = self._runtime.services.get(name, _MISSING)
        self._runtime.services[name] = value

        def restore() -> None:
            if previous is _MISSING:
                self._runtime.services.pop(name, None)
            else:
                self._runtime.services[name] = previous

        self.effect(restore)

    def get(self, socket: str, name: str | None = None) -> Any:
        if name is not None:
            return self._runtime.board.get(socket, name)
        if socket not in self._runtime.services:
            raise NoService(socket)
        return self._runtime.services[socket]

    def module(self, name: str) -> Any:
        """Load a raw leaf capability by its configured plugin name."""
        return self._runtime.board.module(name)

    def load_recipe(self, name: str, path: str) -> Any:
        """Load a lifecycle Recipe through the Host-owned loader."""
        return self._runtime.recipes.load(name, path)

    def has_service(self, name: str) -> bool:
        """Return whether a service is currently available."""
        return name in self._runtime.services

    def on(self, event: str, handler: Callable[..., Any]) -> Cleanup:
        unsubscribe = self._runtime.events.on(event, handler)
        self.effect(unsubscribe)
        return unsubscribe

    def emit(self, event: str, *args: Any, **kwargs: Any) -> list[Any]:
        return self._runtime.events.emit(event, *args, **kwargs)

    def effect(self, cleanup: Cleanup) -> Cleanup:
        if not callable(cleanup):
            raise TypeError("cleanup must be callable")
        if self._owner is not None:
            self._runtime.effects[self._owner].append(cleanup)
        return cleanup

    def unload(self, plugin: str | None = None) -> None:
        if plugin is None:
            try:
                for name in reversed(tuple(self._runtime.order)):
                    self.unload(name)
            finally:
                self._runtime.board.close()
                self._runtime.recipes.close()
            return
        cleanups = self._runtime.effects.pop(plugin, [])
        if plugin in self._runtime.order:
            self._runtime.order.remove(plugin)
        for cleanup in reversed(cleanups):
            cleanup()
