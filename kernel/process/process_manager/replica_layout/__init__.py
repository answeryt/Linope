"""Choose how many copies of one capability to run."""

from kernel.process.process_manager.replica_layout.layout import (
    ReplicaLayout,
    ReplicaPlan,
    ReplicaSpec,
    RunningReplica,
)
from kernel.process.process_manager.replica_layout.registry import (
    layout_names,
    load_layout,
    register_layout,
    unregister_layout,
)

__all__ = [
    "ReplicaLayout",
    "ReplicaPlan",
    "ReplicaSpec",
    "RunningReplica",
    "layout_names",
    "load_layout",
    "register_layout",
    "unregister_layout",
]
