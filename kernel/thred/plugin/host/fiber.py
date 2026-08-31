"""Owner-scoped plugin lifecycle driven by live capability dependencies."""

from __future__ import annotations

import inspect
from collections.abc import Iterable
from typing import Any

from .contracts import Artifact, PluginState, Requirement


class PluginLifecycleError(RuntimeError):
    """A plugin could not be mounted or disposed safely."""


class Fiber:
    """One mounted plugin and every reversible effect it owns."""

    def __init__(
        self,
        context: Any,
        artifact: Artifact,
        plugin: Any,
        config: Any,
        requirements: Iterable[Requirement],
        *,
        parent: "Fiber | None" = None,
    ) -> None:
        self.context = context
        self.artifact = artifact
        self.plugin = plugin
        self.config = config
        self.requirements = tuple(requirements)
        self.parent = parent
        self.children: list[Fiber] = []
        self.state = PluginState.PENDING
        self.error: BaseException | None = None
        self.instance: Any = None
        self._epoch: tuple[tuple[str, tuple[int, ...]], ...] | None = None
        if parent is not None:
            parent.children.append(self)

    @property
    def name(self) -> str:
        return self.artifact.name

    @property
    def missing(self) -> tuple[str, ...]:
        return self.context._runtime.capabilities.missing(self.requirements)

    def reconcile(self) -> bool:
        """Move to the state implied by the current capability topology."""

        if self.state in {
            PluginState.LOADING,
            PluginState.UNLOADING,
            PluginState.DISPOSED,
        }:
            return False
        missing = self.missing
        if missing:
            if self.state in {PluginState.ACTIVE, PluginState.FAILED}:
                self._unload(terminal=False)
                return True
            return False
        epoch = self.context._runtime.capabilities.epoch(self.requirements)
        if self.state is PluginState.ACTIVE and self._epoch != epoch:
            self._unload(terminal=False)
            return True
        if self.state is PluginState.FAILED and self._epoch == epoch:
            return False
        if self.state in {PluginState.PENDING, PluginState.FAILED}:
            self._epoch = epoch
            self._activate()
            return True
        return False

    def dispose(self) -> None:
        """Permanently unload this plugin and all child plugins."""

        if self.state is PluginState.DISPOSED:
            return
        self._unload(terminal=True)
        self.context._reconcile()

    def _activate(self) -> None:
        self.state = PluginState.LOADING
        self.error = None
        scoped = self.context._spawn(self)
        self.context._runtime.mutating += 1
        self.context._runtime.current_owners.append(self)
        try:
            result = _invoke_plugin(self.plugin, scoped, self.config)
            if inspect.isawaitable(result):
                close = getattr(result, "close", None)
                if callable(close):
                    close()
                raise PluginLifecycleError(
                    f"plugin {self.name!r} returned an awaitable from apply; "
                    "plugin activation must synchronously register async resources"
                )
            self.instance = result
            if callable(result) and not inspect.isclass(result):
                scoped.effect(result)
            self.state = PluginState.ACTIVE
        except BaseException as error:
            self.error = error
            try:
                self.context._dispose_owner(self)
            finally:
                self.state = PluginState.FAILED
            raise
        finally:
            self.context._runtime.current_owners.pop()
            self.context._runtime.mutating -= 1

    def _unload(self, *, terminal: bool) -> None:
        self.state = PluginState.UNLOADING
        first_error: BaseException | None = None
        try:
            self.context._runtime.mutating += 1
            for child in reversed(tuple(self.children)):
                try:
                    child.dispose()
                except BaseException as error:
                    first_error = first_error or error
            self.children.clear()
            try:
                self.context._dispose_owner(self)
            except BaseException as error:
                first_error = first_error or error
            self.instance = None
            if terminal:
                self._epoch = None
            self.state = PluginState.DISPOSED if terminal else PluginState.PENDING
            if terminal and self.parent is not None and self in self.parent.children:
                self.parent.children.remove(self)
        finally:
            self.context._runtime.mutating -= 1
        if first_error is not None:
            raise PluginLifecycleError(
                f"plugin {self.name!r} cleanup failed"
            ) from first_error


def _invoke_plugin(plugin: Any, ctx: Any, config: Any) -> Any:
    """Normalize supported syntax to the single ``(ctx, config)`` contract."""

    if inspect.isclass(plugin):
        return plugin(ctx, config)
    apply = getattr(plugin, "apply", None)
    if callable(apply):
        return apply(ctx, config)
    if callable(plugin):
        return plugin(ctx, config)
    raise TypeError(
        "plugin must be a function, class, or object providing apply(ctx, config)"
    )
