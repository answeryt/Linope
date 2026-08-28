# -*- coding: utf-8 -*-
"""Portable Thred definitions and registration without Host dependencies."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from typing import Any


PLUGIN_NAME = "kernel_thred_definition"
PLUGIN_VERSION = "1.0"

LIFETIMES = frozenset({"execution", "thred", "process", "service"})
THRED_DEFINITION_ATTRIBUTE = "__thred_definition__"


def _requirements(values: Iterable[Any], field: str) -> list[Any]:
    if isinstance(values, (str, bytes, bytearray)) or not isinstance(
        values, Iterable
    ):
        raise TypeError(f"{field} must be an iterable")
    return [dict(value) if isinstance(value, Mapping) else value for value in values]


def _handlers(
    handlers: Mapping[str, Callable[..., Any]]
    | Sequence[Callable[..., Any]],
) -> dict[str, Callable[..., Any]]:
    if isinstance(handlers, Mapping):
        items = handlers.items()
    elif isinstance(handlers, Sequence) and not isinstance(
        handlers, (str, bytes, bytearray)
    ):
        items = (
            (getattr(handler, "__name__", ""), handler)
            for handler in handlers
        )
    else:
        raise TypeError("handlers must be a mapping or callable sequence")

    result: dict[str, Callable[..., Any]] = {}
    for interface_name, handler in items:
        if not isinstance(interface_name, str) or not interface_name.strip():
            raise ValueError("handler names must be non-empty strings")
        interface_name = interface_name.strip()
        if interface_name in result:
            raise ValueError(f"duplicate handler name: {interface_name}")
        if not callable(handler):
            raise TypeError(f"handler {interface_name!r} is not callable")
        result[interface_name] = handler
    return result


def _interfaces(
    values: Mapping[str, Mapping[str, Any]] | None,
    handler_names: Iterable[str],
) -> dict[str, dict[str, Any]]:
    if values is not None and not isinstance(values, Mapping):
        raise TypeError("interfaces must be a mapping or None")
    supplied = {} if values is None else values
    names = list(handler_names)
    unknown = set(supplied) - set(names)
    if unknown:
        raise ValueError(
            f"interfaces have no handlers: {sorted(str(name) for name in unknown)}"
        )

    result: dict[str, dict[str, Any]] = {}
    for name in names:
        contract = supplied.get(name, {})
        if not isinstance(contract, Mapping):
            raise TypeError(f"interface {name!r} must be a mapping")
        result[name] = dict(contract)
    return result


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


def define_thred(
    name: str,
    handlers: Mapping[str, Callable[..., Any]]
    | Sequence[Callable[..., Any]],
    interfaces: Mapping[str, Mapping[str, Any]] | None = None,
    version: str = "1",
    retry: Mapping[str, Any] | None = None,
    timeout: int | float | None = None,
    requires: Sequence[Any] = (),
    lifetime: str = "execution",
    release_while_waiting: Sequence[str] = (),
    hooks: Mapping[str, Callable[..., Any]] | None = None,
    **fields: Any,
) -> dict[str, Any]:
    """Create a portable Thred description."""
    if not isinstance(name, str) or not name.strip():
        raise ValueError("name must be a non-empty string")
    if not isinstance(version, str) or not version.strip():
        raise ValueError("version must be a non-empty string")
    if retry is not None and not isinstance(retry, Mapping):
        raise TypeError("retry must be a mapping or None")
    if lifetime not in LIFETIMES:
        raise ValueError(f"lifetime must be one of {sorted(LIFETIMES)}")
    if isinstance(requires, (str, bytes, bytearray)) or not isinstance(
        requires, Sequence
    ):
        raise TypeError("requires must be a sequence")
    if hooks is not None:
        if not isinstance(hooks, Mapping):
            raise TypeError("hooks must be a mapping or None")
        for hook_name, hook in hooks.items():
            if not isinstance(hook_name, str) or not hook_name.strip():
                raise ValueError("hook names must be non-empty strings")
            if not callable(hook):
                raise TypeError(f"hook {hook_name!r} is not callable")

    normalized_handlers = _handlers(handlers)
    definition = dict(fields)
    definition.update(
        {
            "name": name.strip(),
            "version": version.strip(),
            "kind": "thred",
            "interfaces": _interfaces(interfaces, normalized_handlers),
            "handlers": normalized_handlers,
            "retry": dict(retry) if retry is not None else None,
            "timeout": timeout,
            "requires": _requirements(requires, "requires"),
            "lifetime": lifetime,
            "release_while_waiting": _names(
                release_while_waiting, "release_while_waiting"
            ),
            "hooks": dict(hooks or {}),
        }
    )
    return definition


def thred(
    name: str | None = None,
    *,
    handlers: Mapping[str, Callable[..., Any]]
    | Sequence[Callable[..., Any]] = (),
    interfaces: Mapping[str, Mapping[str, Any]] | None = None,
    version: str = "1",
    retry: Mapping[str, Any] | None = None,
    timeout: int | float | None = None,
    requires: Sequence[Any] = (),
    lifetime: str = "execution",
    release_while_waiting: Sequence[str] = (),
    hooks: Mapping[str, Callable[..., Any]] | None = None,
    **fields: Any,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorate a callable as the primary function of a Thred."""

    def decorate(function: Callable[..., Any]) -> Callable[..., Any]:
        if not callable(function):
            raise TypeError("thred can only decorate a callable")
        interface_name = getattr(function, "__name__", "")
        if isinstance(handlers, Mapping):
            bound_handlers: (
                Mapping[str, Callable[..., Any]]
                | Sequence[Callable[..., Any]]
            )
            bound_handlers = dict(handlers)
            if interface_name in bound_handlers:
                raise ValueError(f"duplicate handler name: {interface_name}")
            bound_handlers[interface_name] = function
        else:
            bound_handlers = [function, *handlers]
        definition = define_thred(
            name or interface_name,
            bound_handlers,
            interfaces=interfaces,
            version=version,
            retry=retry,
            timeout=timeout,
            requires=requires,
            lifetime=lifetime,
            release_while_waiting=release_while_waiting,
            hooks=hooks,
            **fields,
        )
        setattr(function, THRED_DEFINITION_ATTRIBUTE, definition)
        return function

    return decorate


class ThredRegistry:
    """Name-and-version registry for Thred descriptions."""

    def __init__(
        self, threds: Iterable[Mapping[str, Any] | Callable[..., Any]] = ()
    ) -> None:
        self._threds: dict[tuple[str, str], dict[str, Any]] = {}
        for definition in threds:
            self.register(definition)

    @staticmethod
    def _definition(
        value: Mapping[str, Any] | Callable[..., Any],
    ) -> dict[str, Any]:
        if isinstance(value, Mapping):
            definition = dict(value)
        elif callable(value):
            attached = getattr(value, THRED_DEFINITION_ATTRIBUTE, None)
            definition = (
                dict(attached)
                if isinstance(attached, Mapping)
                else define_thred(getattr(value, "__name__", ""), [value])
            )
        else:
            raise TypeError("thred must be a definition mapping or callable")

        known_fields = {
            "name",
            "version",
            "kind",
            "interfaces",
            "handlers",
            "retry",
            "timeout",
            "requires",
            "lifetime",
            "release_while_waiting",
            "hooks",
        }
        return define_thred(
            definition.get("name"),
            definition.get("handlers", ()),
            interfaces=definition.get("interfaces"),
            version=definition.get("version", "1"),
            retry=definition.get("retry"),
            timeout=definition.get("timeout"),
            requires=definition.get("requires", ()),
            lifetime=definition.get("lifetime", "execution"),
            release_while_waiting=definition.get("release_while_waiting", ()),
            hooks=definition.get("hooks"),
            **{
                key: item
                for key, item in definition.items()
                if key not in known_fields
            },
        )

    def register(
        self,
        definition: Mapping[str, Any] | Callable[..., Any],
        *,
        replace: bool = False,
    ) -> dict[str, Any]:
        stored = self._definition(definition)
        key = (stored["name"], stored["version"])
        if key in self._threds and not replace:
            raise ValueError(
                f"thred {stored['name']!r} version {stored['version']!r} "
                "is already registered"
            )
        self._threds[key] = stored
        return dict(stored)

    def define(
        self,
        name: str,
        handlers: Mapping[str, Callable[..., Any]]
        | Sequence[Callable[..., Any]],
        interfaces: Mapping[str, Mapping[str, Any]] | None = None,
        version: str = "1",
        **options: Any,
    ) -> dict[str, Any]:
        return self.register(
            define_thred(
                name,
                handlers,
                interfaces=interfaces,
                version=version,
                **options,
            )
        )

    def get(
        self, name: str, version: str = "1", default: Any = None
    ) -> dict[str, Any] | Any:
        definition = self._threds.get((str(name), str(version)))
        return dict(definition) if definition is not None else default

    def require(self, name: str, version: str = "1") -> dict[str, Any]:
        definition = self.get(name, version)
        if definition is None:
            raise KeyError((name, version))
        return definition

    def all(self) -> list[dict[str, Any]]:
        return [dict(definition) for definition in self._threds.values()]

    def __contains__(self, key: object) -> bool:
        if isinstance(key, tuple) and len(key) == 2:
            return (str(key[0]), str(key[1])) in self._threds
        return any(name == str(key) for name, _version in self._threds)

    def __iter__(self):
        return iter(self.all())

    def __len__(self) -> int:
        return len(self._threds)
