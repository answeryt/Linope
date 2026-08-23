# -*- coding: utf-8 -*-
"""Definitions and registration for durable Process functions."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from typing import Any


PLUGIN_NAME = "kernel_process_definition"
PLUGIN_VERSION = "1.0"


def define_process(
    name: str,
    handler: Callable[..., Any],
    *,
    version: str = "1",
    tasks: Sequence[Any] | Mapping[str, Any] = (),
    threads: Sequence[Mapping[str, Any]] = (),
    resources: Sequence[str | Mapping[str, Any]] = (),
    **fields: Any,
) -> dict[str, Any]:
    """Describe a durable process while preserving the original helper API."""
    if not isinstance(name, str) or not name.strip():
        raise ValueError("name is required")
    if not callable(handler):
        raise TypeError("handler must be callable")
    if not isinstance(version, str) or not version.strip():
        raise ValueError("version must be a non-empty string")
    thread_items = [dict(item) for item in threads]
    thread_names = [str(item.get("name") or "") for item in thread_items]
    if any(not item for item in thread_names):
        raise ValueError("every thread must have a name")
    if len(thread_names) != len(set(thread_names)):
        raise ValueError("thread names must be unique within a process")
    task_items = dict(tasks) if isinstance(tasks, Mapping) else list(tasks)
    record = {
        "name": name.strip(),
        "version": version.strip(),
        "handler": handler,
        "tasks": task_items,
        "threads": thread_items,
        "resources": [
            dict(item) if isinstance(item, Mapping) else {"name": str(item), "amount": 1}
            for item in resources
        ],
    }
    record.update(fields)
    return record


class ProcessRegistry:
    """Version-aware collection of injected Process definitions."""

    def __init__(self, processes: Iterable[Any] = ()) -> None:
        self._definitions: dict[tuple[str, str], dict[str, Any]] = {}
        self._latest: dict[str, str] = {}
        for definition in processes:
            self.register(definition)

    def register(
        self,
        definition: Mapping[str, Any] | Callable[..., Any],
        *,
        name: str | None = None,
        version: str = "1",
        tasks: Sequence[Any] | Mapping[str, Any] = (),
        threads: Sequence[Mapping[str, Any]] = (),
        resources: Sequence[str | Mapping[str, Any]] = (),
        **fields: Any,
    ) -> dict[str, Any]:
        if callable(definition) and not isinstance(definition, Mapping):
            attached = getattr(definition, "__process_definition__", None)
            item = (
                dict(attached)
                if isinstance(attached, Mapping) and name is None
                else define_process(
                    name or definition.__name__,
                    definition,
                    version=version,
                    tasks=tasks,
                    threads=threads,
                    resources=resources,
                    **fields,
                )
            )
        elif isinstance(definition, Mapping):
            item = dict(definition)
        else:
            raise TypeError("definition must be a mapping or callable")
        process_name = str(item.get("name") or "").strip()
        process_version = str(item.get("version") or "1").strip()
        if not process_name or not callable(item.get("handler")):
            raise ValueError("definition requires name and callable handler")
        key = (process_name, process_version)
        existing = self._definitions.get(key)
        if existing is not None and existing.get("handler") is not item.get("handler"):
            raise ValueError(
                f"process {process_name!r} version {process_version!r} is registered"
            )
        item["name"] = process_name
        item["version"] = process_version
        item.setdefault("tasks", [])
        item.setdefault("threads", [])
        item.setdefault("resources", [])
        self._definitions[key] = item
        self._latest[process_name] = process_version
        return dict(item)

    def get(self, name: str, version: str | None = None) -> dict[str, Any] | None:
        selected = version or self._latest.get(str(name))
        if selected is None:
            return None
        item = self._definitions.get((str(name), str(selected)))
        return None if item is None else dict(item)

    def require(self, name: str, version: str | None = None) -> dict[str, Any]:
        item = self.get(name, version)
        if item is None:
            suffix = "" if version is None else f" version {version!r}"
            raise KeyError(f"unknown process {name!r}{suffix}")
        return item

    resolve = require

    def decorator(
        self, name: str | None = None, version: str = "1"
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def decorate(handler: Callable[..., Any]) -> Callable[..., Any]:
            definition = define_process(name or handler.__name__, handler, version=version)
            setattr(handler, "__process_definition__", definition)
            self.register(definition)
            return handler

        return decorate

    def values(self) -> list[dict[str, Any]]:
        return [dict(item) for item in self._definitions.values()]

    def __iter__(self) -> Iterator[dict[str, Any]]:
        return iter(self.values())

    def __len__(self) -> int:
        return len(self._definitions)


default_registry = ProcessRegistry()


def process(
    name: str | None = None,
    version: str = "1",
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorate and register a durable Process function."""
    return default_registry.decorator(name=name, version=version)
