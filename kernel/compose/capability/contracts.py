"""Stable re-export of capability contract types."""

from kernel.compose.capability.discovery.contracts import (
    Artifact,
    Cardinality,
    CapabilityRecord,
    PluginDescriptor,
    Requirement,
    cluster_of,
    in_cluster,
    parse_requirements,
)

__all__ = [
    "Artifact",
    "Cardinality",
    "CapabilityRecord",
    "PluginDescriptor",
    "Requirement",
    "cluster_of",
    "in_cluster",
    "parse_requirements",
]
