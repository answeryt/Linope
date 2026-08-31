"""Host facade for capabilities, plugin fibers, events, and unload effects."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Iterable, Mapping
from pathlib import Path
from typing import Any

from .board import create_board
from .capabilities import CapabilityRegistry
from .contracts import Artifact, Capability, PluginState, Requirement
from .events import create_event_manager
from .fiber import Fiber
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
        self.effects: dict[Any, list[Cleanup]] = defaultdict(list)
        self.order: list[Any] = []
        self.fibers: list[Fiber] = []
        self.reconciling = False
        self.mutating = 0
        self.current_owners: list[Any] = []
        self.closed = False
        self.capabilities = CapabilityRegistry(self.capability_changed)
        self.context: Context | None = None

    def capability_changed(self, _name: str) -> None:
        if self.context is not None and not self.mutating:
            self.context._reconcile()


class Context:
    """Public service context passed to every ``apply(ctx, config)`` plugin."""

    def __init__(
        self,
        sockets: Mapping[str, Mapping[str, str]] | None = None,
        *,
        modules: Mapping[str, str] | None = None,
        repo: str | Path | None = None,
        _runtime: _Runtime | None = None,
        _owner: Any = None,
        _fiber: Fiber | None = None,
    ) -> None:
        root = Path(repo) if repo is not None else Path.cwd()
        self._runtime = _runtime or _Runtime(sockets or {}, modules or {}, root)
        self._owner = _owner
        self._fiber = _fiber
        if self._runtime.context is None:
            self._runtime.context = self

    def bind(self, plugin: str) -> "Context":
        if plugin not in self._runtime.order:
            self._runtime.order.append(plugin)
        return Context(_runtime=self._runtime, _owner=plugin)

    def provide(
        self,
        name: str,
        value: Any,
        *,
        contract: str | None = None,
        scope: str = "service",
        replace: bool = True,
    ) -> Cleanup:
        """Publish a capability and tie it to the current plugin lifecycle."""

        provider = self._owner_name
        dispose = self._runtime.capabilities.register(
            name,
            value,
            provider=provider,
            contract=contract,
            scope=scope,
            replace=replace,
        )
        self.effect(dispose)
        return dispose

    def get(self, socket: str, name: str | None = None) -> Any:
        if name is not None:
            return self._runtime.board.get(socket, name)
        try:
            return self._runtime.capabilities.get(socket)
        except LookupError:
            raise NoService(socket)

    def get_all(self, capability: str) -> tuple[Any, ...]:
        """Return all live providers for a multi-valued capability."""

        return self._runtime.capabilities.get_all(capability)

    def capabilities(self, name: str | None = None) -> tuple[Capability, ...]:
        """Describe currently published capabilities."""

        return self._runtime.capabilities.describe(name)

    def module(self, name: str) -> Any:
        """Load a raw leaf capability by its configured plugin name."""
        return self._runtime.board.module(name)

    def load_recipe(self, name: str, path: str) -> Any:
        """Load a lifecycle Recipe through the Host-owned loader."""
        return self._runtime.recipes.load(name, path)

    def has_service(self, name: str) -> bool:
        """Return whether a service is currently available."""
        try:
            self._runtime.capabilities.get(name)
        except LookupError:
            return False
        return True

    def plugin(
        self,
        plugin: Any,
        config: Any = None,
        *,
        name: str | None = None,
        version: str | None = None,
        requirements: Iterable[Requirement | str] | None = None,
        source: str = "",
        kind: str = "recipe",
    ) -> Fiber:
        """Mount a plugin function, class, or ``apply`` object in a Fiber."""

        from .contracts import parse_requirements

        plugin_name = name or getattr(plugin, "PLUGIN_NAME", None)
        if not isinstance(plugin_name, str) or not plugin_name:
            plugin_name = getattr(plugin, "__name__", None)
        if not isinstance(plugin_name, str) or not plugin_name:
            raise ValueError("mounted plugin needs a non-empty name")
        plugin_version = version or getattr(plugin, "PLUGIN_VERSION", "1")
        raw_requirements = (
            requirements
            if requirements is not None
            else getattr(plugin, "PLUGIN_INJECT", ())
        )
        artifact = Artifact(
            plugin_name,
            str(plugin_version),
            source=source,
            kind=kind,
        )
        fiber = Fiber(
            self,
            artifact,
            plugin,
            config,
            parse_requirements(raw_requirements),
            parent=self._fiber,
        )
        self._runtime.fibers.append(fiber)
        self._runtime.order.append(fiber)
        try:
            fiber.reconcile()
            self._reconcile()
        except BaseException:
            if fiber.state is not PluginState.DISPOSED:
                fiber.dispose()
            if fiber in self._runtime.fibers:
                self._runtime.fibers.remove(fiber)
            if fiber in self._runtime.order:
                self._runtime.order.remove(fiber)
            raise
        return fiber

    mount = plugin

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

    def track(self, cleanup: Cleanup) -> Cleanup:
        """Attach a service registration to the currently activating Fiber."""

        if not callable(cleanup):
            raise TypeError("cleanup must be callable")
        owner = (
            self._runtime.current_owners[-1]
            if self._runtime.current_owners
            else self._owner
        )
        if owner is not None:
            self._runtime.effects[owner].append(cleanup)
        return cleanup

    def unload(self, plugin: str | None = None) -> None:
        if plugin is None:
            try:
                for owner in reversed(tuple(self._runtime.order)):
                    if isinstance(owner, Fiber):
                        owner.dispose()
                    else:
                        self.unload(owner)
            finally:
                self._runtime.board.close()
                self._runtime.recipes.close()
                self._runtime.closed = True
            return
        for fiber in reversed(tuple(self._runtime.fibers)):
            if fiber.name == plugin and fiber.state is not PluginState.DISPOSED:
                fiber.dispose()
                if fiber in self._runtime.order:
                    self._runtime.order.remove(fiber)
        self._dispose_owner(plugin)
        if plugin in self._runtime.order:
            self._runtime.order.remove(plugin)

    @property
    def fibers(self) -> tuple[Fiber, ...]:
        """Return every mounted Fiber, including disposed history."""

        return tuple(self._runtime.fibers)

    @property
    def _owner_name(self) -> str:
        if isinstance(self._owner, Fiber):
            return self._owner.name
        if isinstance(self._owner, str):
            return self._owner
        return "<host>"

    def _spawn(self, fiber: Fiber) -> "Context":
        return Context(
            _runtime=self._runtime,
            _owner=fiber,
            _fiber=fiber,
        )

    def _dispose_owner(self, owner: Any) -> None:
        cleanups = self._runtime.effects.pop(owner, [])
        for cleanup in reversed(cleanups):
            cleanup()

    def _reconcile(self) -> None:
        runtime = self._runtime
        if runtime.reconciling or runtime.closed:
            return
        runtime.reconciling = True
        try:
            changed = True
            while changed:
                changed = False
                for fiber in tuple(runtime.fibers):
                    try:
                        changed = fiber.reconcile() or changed
                    except BaseException:
                        # A failed consumer remains observable through its Fiber;
                        # it must not roll back the provider that woke it.
                        changed = True
        finally:
            runtime.reconciling = False
