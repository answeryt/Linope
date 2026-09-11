"""Registered capability classes used as the inventory after import."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from kernel.compose.capability.discovery.contracts import PluginDescriptor
from kernel.compose.capability.capability import Capability
from kernel.compose.capability.graph.composition import DiscoveredCapability


class RegisteredSource:
    """Expose already-imported Capability subclasses as a catalog source."""

    def __init__(self, types: Iterable[type[Capability]] | None = None) -> None:
        self._types = tuple(types) if types is not None else None

    def registered(self) -> tuple[type[Capability], ...]:
        if self._types is not None:
            return self._types
        return Capability.registered()

    def discover(self) -> Iterable[PluginDescriptor]:
        return tuple(
            DiscoveredCapability.from_plugin(item).descriptor for item in self.registered()
        )


class KernelCapabilitySource(RegisteredSource):
    """Built-in compose capabilities imported directly by the host."""

    def __init__(self, _base: Any = None) -> None:
        from kernel.compose.capability.discovery.loader import kernel_capability_types

        super().__init__(kernel_capability_types())


ComposeCoreSource = KernelCapabilitySource
