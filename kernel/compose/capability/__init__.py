"""Public capability kernel: cap bus, capability classes, graph, and injection."""

from kernel.compose.capability.assembly.cap_bus import CapBus
from kernel.compose.capability.assembly.context import CapabilityContext
from kernel.compose.capability.assembly.context import ResourceContainer
from kernel.compose.capability.discovery.loader import inject_capabilities
from kernel.compose.capability.discovery.loader import kernel_capability_types
from kernel.compose.capability.capability import Capability
from kernel.compose.capability.capability import inject
from kernel.compose.capability.graph.composition import CapabilityCatalog
from kernel.compose.capability.graph.composition import CapabilityGraphResolver
from kernel.compose.capability.graph.composition import Composition
from kernel.compose.capability.graph.composition import ComposeResolutionError
from kernel.compose.capability.graph.composition import ComposeSpec

__all__ = [
    "CapBus",
    "Capability",
    "CapabilityCatalog",
    "CapabilityContext",
    "CapabilityGraphResolver",
    "ResourceContainer",
    "Composition",
    "ComposeResolutionError",
    "ComposeSpec",
    "inject",
    "inject_capabilities",
    "kernel_capability_types",
]
