"""Counted copies: fill up to a saved target, and stop anything past that target."""

from __future__ import annotations

from typing import Sequence

from kernel.process.process_manager.replica_layout.layout import (
    ReplicaPlan,
    ReplicaSpec,
    RunningReplica,
    make_replica,
    plan_from_desired,
)

DEFAULT_COUNT = 2


def next_replica_index(used: Sequence[int]) -> int:
    """Smallest number that is not already taken."""
    occupied = set(used)
    index = 0
    while index in occupied:
        index += 1
    return index


def reconcile_count(
    desired: int,
    running: Sequence[int],
) -> tuple[tuple[int, ...], tuple[int, ...]]:
    """Dead numbers are simply absent. Add the lowest free number, or stop the highest extras."""
    if desired < 1:
        raise ValueError("份数至少为 1")
    occupied = set(running)
    if len(occupied) > desired:
        extra = len(occupied) - desired
        highest = sorted(occupied, reverse=True)[:extra]
        return (), tuple(sorted(highest))
    to_start: list[int] = []
    taken = set(occupied)
    while len(taken) < desired:
        index = next_replica_index(tuple(taken))
        to_start.append(index)
        taken.add(index)
    return tuple(to_start), ()


def set_count(count: int, *, singleton: bool) -> int:
    """Reject a target above one when this layout is in single-copy mode."""
    if count < 1:
        raise ValueError("份数至少为 1")
    if singleton and count > 1:
        raise ValueError("单份模式下目标数量不能大于 1")
    return count


def increase_count(count: int, *, singleton: bool, step: int = 1) -> int:
    return set_count(count + step, singleton=singleton)


def decrease_count(count: int, *, singleton: bool, step: int = 1) -> int:
    return set_count(count - step, singleton=singleton)


class CountedLayout:
    """Bring the number of running copies to the saved target."""

    def __init__(self, count: int = DEFAULT_COUNT, singleton: bool = False) -> None:
        self.count = count
        self.singleton = singleton

    def isolated(self) -> "CountedLayout":
        return CountedLayout(self.count, self.singleton)

    def default_settings(self) -> dict[str, int | bool]:
        return {"count": self.count, "singleton": self.singleton}

    def apply_settings(self, settings: dict) -> None:
        if "singleton" in settings:
            self.singleton = bool(settings["singleton"])
        if "count" in settings:
            self.count = set_count(int(settings["count"]), singleton=self.singleton)

    def configure_launch(
        self,
        replica_count: int | None,
        saved_settings: dict[str, object],
    ) -> None:
        self.apply_settings(
            {
                "singleton": saved_settings.get("singleton", self.singleton),
                "count": 1 if replica_count is None else replica_count,
            }
        )

    def set_count(self, count: int) -> int:
        self.count = set_count(count, singleton=self.singleton)
        return self.count

    def increase_count(self, step: int = 1) -> int:
        self.count = increase_count(self.count, singleton=self.singleton, step=step)
        return self.count

    def decrease_count(self, step: int = 1) -> int:
        self.count = decrease_count(self.count, singleton=self.singleton, step=step)
        return self.count

    def desired_replicas(
        self,
        capability: str,
        running: Sequence[RunningReplica],
    ) -> tuple[ReplicaSpec, ...]:
        indexes = [
            int(item.label) for item in running if str(item.label).isdigit()
        ]
        to_start, to_stop = reconcile_count(self.count, indexes)
        stopped = set(to_stop)
        kept = [index for index in indexes if index not in stopped]
        final = sorted(set(kept) | set(to_start))
        by_label = {str(item.label): item for item in running}
        specs: list[ReplicaSpec] = []
        for index in final:
            current = by_label.get(str(index))
            specs.append(
                make_replica(
                    capability,
                    str(index),
                    None if current is None else current.process_id,
                )
            )
        return tuple(specs)

    def plan_replicas(
        self,
        capability: str,
        running: Sequence[RunningReplica],
    ) -> ReplicaPlan:
        return plan_from_desired(self.desired_replicas(capability, running), running)
