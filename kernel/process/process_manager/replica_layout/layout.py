"""Shared replica description. Each layout only depends on this file."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Protocol, Sequence


@dataclass(frozen=True)
class ReplicaSpec:
    """One copy a layout wants: which capability, what it is called, and its process id."""

    capability: str
    replica_name: str
    label: str
    process_id: str


@dataclass(frozen=True)
class RunningReplica:
    """One copy that is already running."""

    capability: str
    replica_name: str
    label: str
    process_id: str


@dataclass(frozen=True)
class ReplicaPlan:
    """What should exist, what to start, and what to stop."""

    desired: tuple[ReplicaSpec, ...]
    to_start: tuple[ReplicaSpec, ...]
    to_stop: tuple[RunningReplica, ...]


class ReplicaLayout(Protocol):
    """Tell the caller which copies should exist, and which to start or stop."""

    def configure_launch(
        self,
        replica_count: int | None,
        saved_settings: dict[str, object],
    ) -> None:
        """Apply this launch's optional count and saved layout settings."""

    def desired_replicas(
        self,
        capability: str,
        running: Sequence[RunningReplica],
    ) -> tuple[ReplicaSpec, ...]:
        ...

    def plan_replicas(
        self,
        capability: str,
        running: Sequence[RunningReplica],
    ) -> ReplicaPlan:
        ...


def make_replica(
    capability: str,
    label: str,
    process_id: str | None = None,
) -> ReplicaSpec:
    """Name a copy `capability-label` and give it its own process id."""
    text = str(label)
    return ReplicaSpec(
        capability=capability,
        replica_name=f"{capability}-{text}",
        label=text,
        process_id=process_id or uuid.uuid4().hex,
    )


def replica_label(capability: str, replica_name: str) -> str:
    """Return the part after `capability-`."""
    prefix = f"{capability}-"
    if replica_name.startswith(prefix):
        return replica_name[len(prefix) :]
    return replica_name


def plan_from_desired(
    desired: Sequence[ReplicaSpec],
    running: Sequence[RunningReplica],
) -> ReplicaPlan:
    """Start desired names that are down. Stop running names that are no longer desired."""
    running_by_name = {item.replica_name: item for item in running}
    aligned: list[ReplicaSpec] = []
    to_start: list[ReplicaSpec] = []
    for spec in desired:
        current = running_by_name.get(spec.replica_name)
        if current is None:
            to_start.append(spec)
            aligned.append(spec)
            continue
        aligned.append(
            ReplicaSpec(
                capability=spec.capability,
                replica_name=spec.replica_name,
                label=spec.label,
                process_id=current.process_id,
            )
        )
    desired_names = {spec.replica_name for spec in desired}
    to_stop = tuple(
        item for item in running if item.replica_name not in desired_names
    )
    return ReplicaPlan(
        desired=tuple(aligned),
        to_start=tuple(to_start),
        to_stop=to_stop,
    )
