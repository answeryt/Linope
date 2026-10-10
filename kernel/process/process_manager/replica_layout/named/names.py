"""Named copies: a new copy is a new name, not the next number."""

from __future__ import annotations

from typing import Sequence

from kernel.process.process_manager.replica_layout.layout import (
    ReplicaPlan,
    ReplicaSpec,
    RunningReplica,
    make_replica,
    plan_from_desired,
)

DEFAULT_NAMES = ("alpha", "beta")


def replicas_by_name(
    capability: str,
    names: Sequence[str],
) -> tuple[ReplicaSpec, ...]:
    """Build one copy per given name."""
    chosen = tuple(str(name) for name in names)
    if len(chosen) != len(set(chosen)):
        raise ValueError("副本名不能重复")
    return tuple(make_replica(capability, name) for name in chosen)


def diff_named_replicas(
    desired_names: Sequence[str],
    running_names: Sequence[str],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Start names in the list that are not running. Stop running names that left the list."""
    desired = set(desired_names)
    running = set(running_names)
    to_start = tuple(sorted(desired - running))
    to_stop = tuple(sorted(running - desired))
    return to_start, to_stop


class NamedLayout:
    """Open the names in the saved list, and close any other running name."""

    def __init__(self, names: Sequence[str] = DEFAULT_NAMES) -> None:
        self.names = tuple(str(name) for name in names)

    def isolated(self) -> "NamedLayout":
        return NamedLayout(self.names)

    def default_settings(self) -> dict[str, list[str]]:
        return {"names": list(self.names)}

    def apply_settings(self, settings: dict) -> None:
        if "names" not in settings:
            return
        self.names = tuple(str(name) for name in settings["names"])
        if len(self.names) != len(set(self.names)):
            raise ValueError("副本名不能重复")

    def configure_launch(
        self,
        replica_count: int | None,
        saved_settings: dict[str, object],
    ) -> None:
        del saved_settings
        count = 1 if replica_count is None else replica_count
        if count < 1:
            raise ValueError("份数至少为 1")
        self.apply_settings({"names": [str(index) for index in range(count)]})

    def desired_replicas(
        self,
        capability: str,
        running: Sequence[RunningReplica],
    ) -> tuple[ReplicaSpec, ...]:
        del running
        return replicas_by_name(capability, self.names)

    def plan_replicas(
        self,
        capability: str,
        running: Sequence[RunningReplica],
    ) -> ReplicaPlan:
        return plan_from_desired(self.desired_replicas(capability, running), running)
