"""Capability registry with reversible, owner-scoped registrations."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Iterable
from typing import Any

from kernel.compose.capability.discovery.contracts import CapabilityRecord, Cardinality, Requirement


class CapabilityConflict(RuntimeError):
    """A single-valued capability already has another provider."""


class CapabilityRegistry:
    """Store capability values independently of provider implementation."""

    def __init__(self, changed: Callable[[str], None]) -> None:
        self._by_key: dict[str, list[CapabilityRecord]] = defaultdict(list)
        self._by_alias: dict[str, list[CapabilityRecord]] = defaultdict(list)
        self._changed = changed

    def register(
        self,
        key: str,
        value: Any,
        *,
        provider: str,
        contract: str | None = None,
        scope: str = "service",
        replace: bool = False,
        aliases: Iterable[str] = (),
    ) -> Callable[[], None]:
        capability = CapabilityRecord(key, value, provider, contract, scope)
        names = tuple(dict.fromkeys((key, *(str(item) for item in aliases if item))))
        current = self._by_key[key]
        if current and not replace:
            raise CapabilityConflict(
                f"capability {key!r} is already provided by {current[-1].provider!r}"
            )
        current.append(capability)
        for name in names:
            self._by_alias[name].append(capability)
        self._changed(key)
        disposed = False

        def dispose() -> None:
            nonlocal disposed
            if disposed:
                return
            disposed = True
            values = self._by_key.get(key)
            if values is not None:
                try:
                    values.remove(capability)
                except ValueError:
                    pass
                else:
                    if not values:
                        self._by_key.pop(key, None)
            for name in names:
                aliased = self._by_alias.get(name)
                if aliased is None:
                    continue
                try:
                    aliased.remove(capability)
                except ValueError:
                    continue
                if not aliased:
                    self._by_alias.pop(name, None)
            self._changed(key)

        return dispose

    def get(self, key: str) -> Any:
        values = self._by_key.get(key) or self._by_alias.get(key)
        if not values:
            raise LookupError(f"no capability named {key!r}")
        return values[-1].value

    def get_all(self, key: str) -> tuple[Any, ...]:
        seen: list[CapabilityRecord] = []
        for item in self._by_alias.get(key, ()):
            if item not in seen:
                seen.append(item)
        if not seen:
            seen = list(self._by_key.get(key, ()))
        return tuple(item.value for item in seen)

    def capabilities(self, key: str | None = None) -> tuple[CapabilityRecord, ...]:
        if key is not None:
            return tuple(self._by_alias.get(key, self._by_key.get(key, ())))
        return tuple(
            capability for capabilities in self._by_key.values() for capability in capabilities
        )

    def satisfies(self, requirement: Requirement) -> bool:
        if requirement.optional:
            return True
        values = self._by_alias.get(requirement.capability) or self._by_key.get(
            requirement.capability, ()
        )
        return bool(values)

    def missing(self, requirements: Iterable[Requirement]) -> tuple[str, ...]:
        return tuple(
            requirement.capability
            for requirement in requirements
            if not self.satisfies(requirement)
        )
