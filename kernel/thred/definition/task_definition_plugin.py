# -*- coding: utf-8 -*-
"""Portable task definitions and registration without Host dependencies."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from typing import Any


PLUGIN_NAME = "kernel_task_definition"
PLUGIN_VERSION = "1.0"

LIFETIMES = frozenset({"execution", "task", "process", "service"})
TASK_DEFINITION_ATTRIBUTE = "__task_definition__"


def _requirements(values: Iterable[Any], field: str) -> list[Any]:
    if isinstance(values, (str, bytes, bytearray)) or not isinstance(
        values, Iterable
    ):
        raise TypeError(f"{field} must be an iterable")
    return [dict(value) if isinstance(value, Mapping) else value for value in values]


def define_task(
    name: str,
    function: Callable[..., Any],
    version: str = "1",
    retry: Mapping[str, Any] | None = None,
    timeout: int | float | None = None,
    resources: Iterable[str | Mapping[str, Any]] = (),
    **fields: Any,
) -> dict[str, Any]:
    """Build a task definition whose callable remains owned by the Host."""
    if not isinstance(name, str) or not name.strip():
        raise ValueError("name must be a non-empty string")
    if not callable(function):
        raise TypeError("function must be callable")
    if not isinstance(version, str) or not version.strip():
        raise ValueError("version must be a non-empty string")
    if retry is not None and not isinstance(retry, Mapping):
        raise TypeError("retry must be a mapping or None")

    definition = dict(fields)
    definition.update(
        {
            "name": name.strip(),
            "version": version.strip(),
            "function": function,
            "retry": dict(retry) if retry is not None else None,
            "timeout": timeout,
            "resources": _requirements(resources, "resources"),
            "kind": "task",
        }
    )
    return definition


def task(
    name: str | None = None,
    version: str = "1",
    retry: Mapping[str, Any] | None = None,
    timeout: int | float | None = None,
    resources: Iterable[str | Mapping[str, Any]] = (),
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorate a callable with the task definition consumed by executors."""

    def decorate(function: Callable[..., Any]) -> Callable[..., Any]:
        definition = define_task(
            name or getattr(function, "__name__", ""),
            function,
            version=version,
            retry=retry,
            timeout=timeout,
            resources=resources,
        )
        setattr(function, TASK_DEFINITION_ATTRIBUTE, definition)
        return function

    return decorate


class TaskRegistry:
    """Name-and-version registry for task definitions."""

    def __init__(self, tasks: Iterable[Mapping[str, Any] | Callable[..., Any]] = ()):
        self._tasks: dict[tuple[str, str], dict[str, Any]] = {}
        for definition in tasks:
            self.register(definition)

    @staticmethod
    def _definition(
        value: Mapping[str, Any] | Callable[..., Any],
    ) -> dict[str, Any]:
        if isinstance(value, Mapping):
            definition = dict(value)
        elif callable(value):
            attached = getattr(value, TASK_DEFINITION_ATTRIBUTE, None)
            if not isinstance(attached, Mapping):
                definition = define_task(
                    getattr(value, "__name__", ""), value
                )
            else:
                definition = dict(attached)
        else:
            raise TypeError("task must be a definition mapping or callable")

        name = definition.get("name")
        version = definition.get("version", "1")
        function = definition.get("function")
        if not isinstance(name, str) or not name.strip():
            raise ValueError("task definition is missing a non-empty name")
        if not isinstance(version, str) or not version.strip():
            raise ValueError("task definition is missing a non-empty version")
        if not callable(function):
            raise TypeError("task definition is missing a callable function")
        definition["name"] = name.strip()
        definition["version"] = version.strip()
        definition.setdefault("retry", None)
        definition.setdefault("timeout", None)
        definition.setdefault("resources", [])
        definition.setdefault("kind", "task")
        return definition

    def register(
        self,
        definition: Mapping[str, Any] | Callable[..., Any],
        *,
        replace: bool = False,
    ) -> dict[str, Any]:
        stored = self._definition(definition)
        key = (stored["name"], stored["version"])
        if key in self._tasks and not replace:
            raise ValueError(
                f"task {stored['name']!r} version {stored['version']!r} "
                "is already registered"
            )
        self._tasks[key] = stored
        return dict(stored)

    def define(
        self,
        name: str,
        function: Callable[..., Any],
        version: str = "1",
        **options: Any,
    ) -> dict[str, Any]:
        definition = define_task(name, function, version=version, **options)
        return self.register(definition)

    def get(
        self, name: str, version: str = "1", default: Any = None
    ) -> dict[str, Any] | Any:
        definition = self._tasks.get((str(name), str(version)))
        return dict(definition) if definition is not None else default

    def require(self, name: str, version: str = "1") -> dict[str, Any]:
        definition = self.get(name, version)
        if definition is None:
            raise KeyError((name, version))
        return definition

    def all(self) -> list[dict[str, Any]]:
        return [dict(definition) for definition in self._tasks.values()]

    def __contains__(self, key: object) -> bool:
        if isinstance(key, tuple) and len(key) == 2:
            return (str(key[0]), str(key[1])) in self._tasks
        return any(name == str(key) for name, _version in self._tasks)

    def __iter__(self):
        return iter(self.all())

    def __len__(self) -> int:
        return len(self._tasks)


def _function_exports(
    functions: Mapping[str, Callable[..., Any]]
    | Sequence[Callable[..., Any]],
) -> dict[str, Callable[..., Any]]:
    if isinstance(functions, Mapping):
        items = functions.items()
    elif isinstance(functions, Sequence) and not isinstance(
        functions, (str, bytes, bytearray)
    ):
        items = (
            (getattr(function, "__name__", ""), function)
            for function in functions
        )
    else:
        raise TypeError("functions must be a mapping or callable sequence")

    exports: dict[str, Callable[..., Any]] = {}
    for export_name, function in items:
        if not isinstance(export_name, str) or not export_name.strip():
            raise ValueError("function export names must be non-empty strings")
        export_name = export_name.strip()
        if export_name in exports:
            raise ValueError(f"duplicate function export name: {export_name}")
        if not callable(function):
            raise TypeError(f"function export {export_name!r} is not callable")
        exports[export_name] = function
    return exports


def _names(values: Sequence[str], field: str) -> list[str]:
    if isinstance(values, (str, bytes, bytearray)) or not isinstance(
        values, Sequence
    ):
        raise TypeError(f"{field} must be a sequence")
    result: list[str] = []
    for value in values:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field} entries must be non-empty strings")
        result.append(value.strip())
    return result


def define_thread(
    name: str,
    functions: Mapping[str, Callable[..., Any]]
    | Sequence[Callable[..., Any]],
    requires: Sequence[Any] = (),
    lifetime: str = "execution",
    release_while_waiting: Sequence[str] = (),
    hooks: Mapping[str, Callable[..., Any]] | None = None,
    **fields: Any,
) -> dict[str, Any]:
    """Compatibility definition matching the legacy Thread plugin contract."""
    if not isinstance(name, str) or not name.strip():
        raise ValueError("name must be a non-empty string")
    if lifetime not in LIFETIMES:
        raise ValueError(f"lifetime must be one of {sorted(LIFETIMES)}")
    if isinstance(requires, (str, bytes, bytearray)) or not isinstance(
        requires, Sequence
    ):
        raise TypeError("requires must be a sequence")
    requirements = _requirements(requires, "requires")
    if hooks is not None:
        if not isinstance(hooks, Mapping):
            raise TypeError("hooks must be a mapping or None")
        for hook_name, hook in hooks.items():
            if not isinstance(hook_name, str) or not hook_name.strip():
                raise ValueError("hook names must be non-empty strings")
            if not callable(hook):
                raise TypeError(f"hook {hook_name!r} is not callable")

    definition = {
        "name": name.strip(),
        "kind": "thread",
        "functions": _function_exports(functions),
        "requires": requirements,
        "lifetime": lifetime,
        "release_while_waiting": _names(
            release_while_waiting, "release_while_waiting"
        ),
        "hooks": dict(hooks or {}),
    }
    definition.update(fields)
    return definition
