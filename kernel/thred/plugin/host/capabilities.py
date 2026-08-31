"""Live capability registry with reversible, owner-scoped registrations."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Iterable
from typing import Any

from .contracts import Capability, Cardinality, Requirement


class CapabilityConflict(RuntimeError):
    """A single-valued capability already has another provider."""


class CapabilityRegistry:
    """Store capability generations independently of plugin implementation."""

    def __init__(self, changed: Callable[[str], None]) -> None:
        self._by_key: dict[str, list[Capability]] = defaultdict(list)
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
    ) -> Callable[[], None]:
        capability = Capability(key, value, provider, contract, scope)
        current = self._by_key[key]
        if current and not replace:
            raise CapabilityConflict(
                f"capability {key!r} is already provided by {current[-1].provider!r}"
            )
        current.append(capability)
        self._changed(key)
        disposed = False

        def dispose() -> None:
            nonlocal disposed
            if disposed:
                return
            disposed = True
            values = self._by_key.get(key)
            if values is None:
                return
            try:
                values.remove(capability)
            except ValueError:
                return
            if not values:
                self._by_key.pop(key, None)
            self._changed(key)

        return dispose

    def get(self, key: str) -> Any:
        values = self._by_key.get(key)
        if not values:
            raise LookupError(f"no capability named {key!r}")
        return values[-1].value

    def get_all(self, key: str) -> tuple[Any, ...]:
        return tuple(item.value for item in self._by_key.get(key, ()))

    def describe(self, key: str | None = None) -> tuple[Capability, ...]:
        if key is not None:
            return tuple(self._by_key.get(key, ()))
        return tuple(
            capability
            for capabilities in self._by_key.values()
            for capability in capabilities
        )

    def satisfies(self, requirement: Requirement) -> bool:
        if requirement.optional:
            return True
        values = self._by_key.get(requirement.capability, ())
        if requirement.cardinality is Cardinality.MANY:
            return bool(values)
        return bool(values)

    def missing(self, requirements: Iterable[Requirement]) -> tuple[str, ...]:
        return tuple(
            requirement.capability
            for requirement in requirements
            if not self.satisfies(requirement)
        )

    def epoch(
        self, requirements: Iterable[Requirement]
    ) -> tuple[tuple[str, tuple[int, ...]], ...]:
        """Return provider identities used to detect live dependency replacement."""

        return tuple(
            (
                requirement.capability,
                self._requirement_epoch(requirement),
            )
            for requirement in requirements
            if not requirement.optional
        )

    def _requirement_epoch(self, requirement: Requirement) -> tuple[int, ...]:
        values = self._by_key.get(requirement.capability, ())
        if requirement.cardinality is Cardinality.MANY:
            return tuple(id(capability) for capability in values)
        return (id(values[-1]),) if values else ()
