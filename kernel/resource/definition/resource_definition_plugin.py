# -*- coding: utf-8 -*-
"""Declarative resource definitions with Host-injected lifecycle hooks."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


PLUGIN_NAME = "kernel_resource_definition"
PLUGIN_VERSION = "1.0"

SCOPES = frozenset({"execution", "task", "process", "service"})
PERSISTENCE_MODES = frozenset({"ephemeral", "persistent"})
RESOURCE_KINDS = frozenset({"container", "model"})


def _required_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def define_resource(
    name: str,
    kind: str = "container",
    capacity: int | float | None = None,
    scope: str = "service",
    persistence: str = "persistent",
    shareable: bool = True,
    acquire: Callable[..., Any] | None = None,
    release: Callable[..., Any] | None = None,
    **fields: Any,
) -> dict[str, Any]:
    """Build a resource definition without importing a concrete Host runtime."""
    name = _required_text(name, "name")
    kind = _required_text(kind, "kind")
    if kind not in RESOURCE_KINDS:
        raise ValueError(f"kind must be one of {sorted(RESOURCE_KINDS)}")
    if scope not in SCOPES:
        raise ValueError(f"scope must be one of {sorted(SCOPES)}")
    if persistence not in PERSISTENCE_MODES:
        raise ValueError(
            f"persistence must be one of {sorted(PERSISTENCE_MODES)}"
        )
    if isinstance(capacity, bool) or (
        capacity is not None and not isinstance(capacity, (int, float))
    ):
        raise TypeError("capacity must be an int, float, or None")
    if capacity is not None and capacity < 0:
        raise ValueError("capacity must be non-negative")
    if not isinstance(shareable, bool):
        raise TypeError("shareable must be a bool")
    if acquire is not None and not callable(acquire):
        raise TypeError("acquire must be callable or None")
    if release is not None and not callable(release):
        raise TypeError("release must be callable or None")

    definition = {
        "name": name,
        "kind": kind,
        "capacity": capacity,
        "scope": scope,
        "persistence": persistence,
        "shareable": shareable,
        "acquire": acquire,
        "release": release,
    }
    definition.update(fields)
    return definition
