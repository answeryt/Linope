"""Class-based capabilities that join the cap bus on injection."""

from __future__ import annotations

import sys
from collections.abc import Mapping, Sequence
from typing import Any, ClassVar

from kernel.compose.capability.discovery.contracts import (
    Cardinality,
    Requirement,
    in_cluster,
    parse_requirements,
)


class Capability:
    """Capability author surface: subclass, inject, and the bus subscription is automatic."""

    name: ClassVar[str] = ""
    version: ClassVar[str] = "1.0"
    kind: ClassVar[str] = "capability"
    provides: ClassVar[tuple[str, ...]] = ()
    requires: ClassVar[tuple[Any, ...]] = ()
    constraints: ClassVar[Mapping[str, Any]] = {}
    config: ClassVar[Any] = None
    priority: ClassVar[int] = 0

    _registry: ClassVar[dict[str, type["Capability"]]] = {}

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        declared = cls.__dict__.get("name")
        if not isinstance(declared, str) or not declared:
            return
        module = cls.__module__
        if module.startswith("kernel.") or module.startswith("capability."):
            Capability._registry[declared] = cls

    def __init__(self) -> None:
        self._requirements = tuple(parse_requirements(type(self).requires))

    @classmethod
    def registered(cls) -> tuple[type["Capability"], ...]:
        return tuple(cls._registry.values())

    @property
    def identity(self) -> str:
        return f"{self.name}:{self.version}"

    @property
    def requirement_list(self) -> tuple[Requirement, ...]:
        return self._requirements

    def provide_keys(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys((*self.provides, self.name)))

    def satisfies(self, requirement: Requirement | str) -> bool:
        key = requirement.capability if isinstance(requirement, Requirement) else requirement
        candidates = (self.name, self.kind, *self.provides)
        return any(item == key or in_cluster(item, key) for item in candidates if item)

    def on_injected(self, context: Any) -> None:
        bus = context.cap_bus
        for key in self.provide_keys():
            bus.subscribe(self, capability=key, name=self.name, weak=False)
        self.activate(context)

    def on_request(self, context: Any, broadcast: Any) -> Any:
        bound = context.bind(self.identity)
        needed = broadcast.capability if getattr(broadcast, "capability", None) else self.name
        if not context.has_service(needed):
            self.activate(bound)
        return {"handled": True, "owners": (self.identity,)}

    def activate(self, context: Any) -> None:
        value = self.payload()
        if value is None:
            return
        keys = self.provide_keys()
        primary = self.name if self.name in keys else keys[0]
        aliases = tuple(key for key in keys if key != primary)
        context.provide(primary, value, aliases=aliases)

    def payload(self) -> Any:
        return sys.modules.get(self.__class__.__module__)


def inject(capability: Capability, target: Any) -> Capability:
    """Bind one capability onto a composition or resource container and auto-subscribe."""

    context = getattr(target, "res", target)
    owner = capability.identity
    if context.is_owner_loaded(owner):
        return capability
    bound = context.bind(owner)
    bound.mark_owner_loaded(owner)
    injected = getattr(context._runtime, "injected", None)
    if injected is None:
        context._runtime.injected = []
        injected = context._runtime.injected
    injected.append(capability)
    capability.on_injected(bound)
    return capability


def ordered_capability_types(
    types: Sequence[type[Capability]],
) -> tuple[type[Capability], ...]:
    """Stable dependency order so required providers activate before dependents."""

    remaining: list[type[Capability]] = list(dict.fromkeys(types))
    provided: set[str] = set()
    ordered: list[type[Capability]] = []
    while remaining:
        ready = [
            item
            for item in remaining
            if _requirements_ready(item, provided, remaining)
        ]
        if not ready:
            ready = [min(remaining, key=lambda item: item.name)]
        ready.sort(key=lambda item: (-int(item.priority), item.name))
        for item in ready:
            remaining.remove(item)
            ordered.append(item)
            provided.update(_provided_names(item))
    return tuple(ordered)


def _provided_names(item: type[Capability]) -> tuple[str, ...]:
    return tuple(dict.fromkeys((item.name, item.kind, *item.provides)))


def _type_satisfies(item: type[Capability], requirement: Requirement) -> bool:
    key = requirement.capability
    candidates = (item.name, item.kind, *item.provides)
    return any(name == key or in_cluster(name, key) for name in candidates if name)


def _requirements_ready(
    item: type[Capability],
    provided: set[str],
    remaining: Sequence[type[Capability]],
) -> bool:
    others = [other for other in remaining if other is not item]
    for requirement in parse_requirements(item.requires):
        if requirement.optional:
            continue
        already = any(
            name == requirement.capability or in_cluster(name, requirement.capability)
            for name in provided
        )
        pending = any(_type_satisfies(other, requirement) for other in others)
        if requirement.cardinality is Cardinality.MANY:
            if pending:
                return False
            continue
        if already:
            continue
        return False
    return True
