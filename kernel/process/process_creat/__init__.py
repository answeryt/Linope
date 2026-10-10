"""Discover capability definitions used to launch capability processes."""

from kernel.process.process_creat.activation import ProcessActivation
from kernel.process.process_creat.creator import ProcessCreator
from kernel.process.process_creat.instances import (
    CapabilityDefinition,
    describe_instance,
    discover_instances,
    load_instance,
    resolve_instance_id,
)
from kernel.process.process_creat.strategy import launch_detached

__all__ = [
    "ProcessActivation",
    "ProcessCreator",
    "launch_detached",
    "CapabilityDefinition",
    "describe_instance",
    "discover_instances",
    "load_instance",
    "resolve_instance_id",
]
