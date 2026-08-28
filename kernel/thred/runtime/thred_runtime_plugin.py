# -*- coding: utf-8 -*-
"""Compile independently selected Thred capabilities into one small facade."""

from __future__ import annotations

import inspect
from collections.abc import Callable, Mapping, Sequence
from functools import wraps
from typing import Any


PLUGIN_NAME = "kernel_thred_runtime"
PLUGIN_VERSION = "1.0"


async def _await_if_needed(value: Any) -> Any:
    return await value if inspect.isawaitable(value) else value


def _callable(component: Any, name: str) -> Callable[..., Any]:
    value = getattr(component, name, None)
    if not callable(value):
        raise TypeError(f"component must provide callable {name}")
    return value


def _executor(component: Any, resources: Any) -> tuple[Any, Callable[..., Any]]:
    factory = getattr(component, "ThredExecutor", None)
    instance = factory(resources=resources) if callable(factory) else component
    execute = getattr(instance, "execute", None)
    if not callable(execute) and callable(instance):
        execute = instance
    if not callable(execute):
        raise TypeError(
            "executor must be callable, provide execute, or provide ThredExecutor"
        )
    return instance, execute


class ThredRuntime:
    """Facade compiled from replaceable definition, execution, and binding APIs."""

    def __init__(
        self,
        *,
        definition: Any,
        registry: Any,
        executor: Any,
        execute: Callable[..., Any],
        binding: Any = None,
    ) -> None:
        self.definition = definition
        self.registry = registry
        self.executor = executor
        self.binding = binding
        self._execute = execute

        self.define_thred = _callable(definition, "define_thred")
        definition_thred = _callable(definition, "thred")
        self.register = _callable(registry, "register")
        self.get = _callable(registry, "get")
        self.require = _callable(registry, "require")
        self.all = _callable(registry, "all")

        @wraps(definition_thred)
        def registered_thred(*args: Any, **kwargs: Any) -> Callable[..., Any]:
            decorate = definition_thred(*args, **kwargs)

            def register(function: Callable[..., Any]) -> Callable[..., Any]:
                decorated = decorate(function)
                self.register(decorated)
                return decorated

            return register

        self.thred = registered_thred
        self._define = _callable(registry, "define")

        self._build_binding = (
            _callable(binding, "build_binding") if binding is not None else None
        )
        self._bind = (
            _callable(binding, "bind_resources") if binding is not None else None
        )
        self._release = (
            _callable(binding, "release_resources") if binding is not None else None
        )

    def __call__(self, *args: Any, **kwargs: Any) -> Callable[..., Any]:
        """Decorate and register a Thred using the Definition `@thred` API."""
        return self.thred(*args, **kwargs)

    def define(
        self,
        name: str,
        handlers: Mapping[str, Callable[..., Any]]
        | Sequence[Callable[..., Any]]
        | Callable[..., Any],
        interfaces: Mapping[str, Mapping[str, Any]] | None = None,
        version: str = "1",
        **options: Any,
    ) -> dict[str, Any]:
        bound_handlers = [handlers] if callable(handlers) else handlers
        return self._define(
            name,
            bound_handlers,
            interfaces=interfaces,
            version=version,
            **options,
        )

    async def execute(
        self,
        thred: str | Mapping[str, Any] | Callable[..., Any],
        input: Any = None,
        *,
        version: str = "1",
        context: Any = None,
        resources: Any = None,
        interface: str | None = None,
    ) -> Any:
        definition = self.require(thred, version) if isinstance(thred, str) else thred
        return await _await_if_needed(
            self._execute(
                definition,
                input=input,
                context=context,
                resources=resources,
                interface=interface,
            )
        )

    def build_binding(
        self,
        thred: Mapping[str, Any],
        process_id: str,
        binding_id: str | None = None,
    ) -> dict[str, Any]:
        if self._build_binding is None:
            raise RuntimeError("this Thred runtime has no binding component")
        return self._build_binding(thred, process_id, binding_id)

    async def bind(
        self,
        value: Mapping[str, Any],
        pool: Any,
        owner_id: str | None = None,
    ) -> dict[str, Any]:
        if self._bind is None:
            raise RuntimeError("this Thred runtime has no binding component")
        return await _await_if_needed(self._bind(value, pool, owner_id))

    async def release(
        self,
        value: Mapping[str, Any],
        pool: Any,
    ) -> dict[str, Any]:
        if self._release is None:
            raise RuntimeError("this Thred runtime has no binding component")
        return await _await_if_needed(self._release(value, pool))


def compile_runtime(
    *,
    definition: Any,
    executor: Any,
    binding: Any = None,
    registry: Any = None,
    resources: Any = None,
    extensions: Sequence[Callable[[ThredRuntime], Any]] = (),
) -> ThredRuntime:
    """Compile selected capabilities while preserving the Definition API."""
    registry_factory = getattr(definition, "ThredRegistry", None)
    selected_registry = (
        registry_factory()
        if registry is None and callable(registry_factory)
        else registry
    )
    if selected_registry is None:
        raise TypeError("definition must provide ThredRegistry or registry is required")

    selected_executor, execute = _executor(executor, resources)
    runtime = ThredRuntime(
        definition=definition,
        registry=selected_registry,
        executor=selected_executor,
        execute=execute,
        binding=binding,
    )
    for extension in extensions:
        if not callable(extension):
            raise TypeError("runtime extensions must be callable")
        extension(runtime)
    return runtime
