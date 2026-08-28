"""Validation for lifecycle-aware composition plugins loaded by the Host."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from types import ModuleType
from typing import Any


class ProtocolError(ValueError):
    """A module does not satisfy the Host composition contract."""


def plugin_name(module: ModuleType) -> str:
    name = getattr(module, "PLUGIN_NAME", None)
    if not isinstance(name, str) or not name:
        raise ProtocolError("PLUGIN_NAME must be a non-empty string")
    return name


def inject_names(module: ModuleType) -> tuple[str, ...]:
    raw = getattr(module, "PLUGIN_INJECT", ())
    if raw is None:
        return ()
    if isinstance(raw, str) or not isinstance(raw, Sequence):
        raise ProtocolError(f"{plugin_name(module)} PLUGIN_INJECT must be a sequence")
    names = tuple(raw)
    if any(not isinstance(name, str) or not name for name in names):
        raise ProtocolError(
            f"{plugin_name(module)} PLUGIN_INJECT must contain non-empty strings"
        )
    return names


def plugin_config(module: ModuleType) -> Any:
    return getattr(module, "PLUGIN_CONFIG", None)


def apply_function(module: ModuleType) -> Callable[[Any, Any], Any]:
    apply = getattr(module, "apply", None)
    if not callable(apply):
        raise ProtocolError(f"{plugin_name(module)} is missing apply(lip, config)")
    return apply


def validate(module: ModuleType, expected_name: str) -> None:
    actual = plugin_name(module)
    if actual != expected_name:
        raise ProtocolError(
            f"PLUGIN_NAME must be {expected_name!r}, got {actual!r}"
        )
    inject_names(module)
    apply_function(module)
