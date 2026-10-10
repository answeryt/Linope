"""Numbered copies: slots are fixed, and an empty slot is filled with the same number."""

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


def _names_distinguish_numbers(capability: str, names: Sequence[str]) -> bool:
    suffixes: list[str] = []
    for name in names:
        base, separator, suffix = name.rpartition("-")
        if separator != "-" or not suffix.isdigit() or base != capability:
            return False
        suffixes.append(suffix)
    return len(suffixes) == len(set(suffixes))


def expand_numbered_replicas(
    capability: str,
    count: int,
    start: int = 0,
    names: Sequence[str] | None = None,
) -> tuple[ReplicaSpec, ...]:
    """Expand one capability into fixed slots. Count stays the same while running."""
    if count < 1:
        raise ValueError("份数至少为 1")
    if names is None:
        chosen = tuple(
            f"{capability}-{index}" for index in range(start, start + count)
        )
    else:
        chosen = tuple(names)
        if len(chosen) != count:
            raise ValueError("副本名数量和份数不一致")
    if count > 1 and not _names_distinguish_numbers(capability, chosen):
        raise ValueError("数量大于 1 时副本名必须能区分编号")
    return tuple(
        make_replica(capability, name[len(capability) + 1 :])
        for name in chosen
    )


class NumberedLayout:
    """Keep a fixed list of numbers. Refill a hole with that same number."""

    def __init__(self, count: int = DEFAULT_COUNT, start: int = 0) -> None:
        self.count = count
        self.start = start

    def isolated(self) -> "NumberedLayout":
        return NumberedLayout(self.count, self.start)

    def default_settings(self) -> dict[str, int]:
        return {"count": self.count, "start": self.start}

    def apply_settings(self, settings: dict) -> None:
        if "count" in settings:
            self.count = int(settings["count"])
        if "start" in settings:
            self.start = int(settings["start"])
        if self.count < 1:
            raise ValueError("份数至少为 1")

    def configure_launch(
        self,
        replica_count: int | None,
        saved_settings: dict[str, object],
    ) -> None:
        self.apply_settings(
            {
                "count": 1 if replica_count is None else replica_count,
                "start": saved_settings.get("start", 0),
            }
        )

    def desired_replicas(
        self,
        capability: str,
        running: Sequence[RunningReplica],
    ) -> tuple[ReplicaSpec, ...]:
        del running
        return expand_numbered_replicas(capability, self.count, self.start)

    def plan_replicas(
        self,
        capability: str,
        running: Sequence[RunningReplica],
    ) -> ReplicaPlan:
        return plan_from_desired(self.desired_replicas(capability, running), running)
