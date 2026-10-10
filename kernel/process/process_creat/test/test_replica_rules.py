"""Rules for numbered, counted, and named copies."""

import pytest

from kernel.process.process_manager.replica_layout.counted.count import (
    decrease_count,
    increase_count,
    next_replica_index,
    reconcile_count,
    set_count,
)
from kernel.process.process_manager.replica_layout.layout import RunningReplica
from kernel.process.process_manager.replica_layout.named.names import (
    diff_named_replicas,
    replicas_by_name,
)
from kernel.process.process_manager.replica_layout.numbered.expand import (
    NumberedLayout,
    expand_numbered_replicas,
)
from kernel.process.process_manager.replica_layout.registry import load_layout
from kernel.process.reconcile import _apply_replica_count


def test_numbered_rejects_names_that_do_not_distinguish_slots() -> None:
    with pytest.raises(ValueError, match="区分编号"):
        expand_numbered_replicas(
            "tools.bash",
            2,
            names=("tools.bash", "tools.bash-1"),
        )


def test_numbered_expands_two_different_names() -> None:
    specs = expand_numbered_replicas("tools.bash", 2)
    assert [item.replica_name for item in specs] == ["tools.bash-0", "tools.bash-1"]
    assert specs[0].process_id != specs[1].process_id


def test_numbered_refills_the_empty_slot() -> None:
    running = (
        RunningReplica(
            capability="tools.bash",
            replica_name="tools.bash-1",
            label="1",
            process_id="still-alive",
        ),
    )
    plan = NumberedLayout(count=2).plan_replicas("tools.bash", running)
    assert [item.replica_name for item in plan.to_start] == ["tools.bash-0"]
    assert plan.to_stop == ()
    assert any(item.process_id == "still-alive" for item in plan.desired)


def test_counted_fills_a_hole_and_stops_extras() -> None:
    assert next_replica_index([0, 2]) == 1
    to_start, to_stop = reconcile_count(2, [1])
    assert to_start == (0,)
    assert to_stop == ()
    to_start, to_stop = reconcile_count(2, [0, 1, 3])
    assert to_start == ()
    assert to_stop == (3,)


def test_counted_singleton_rejects_more_than_one() -> None:
    with pytest.raises(ValueError, match="单份模式"):
        set_count(2, singleton=True)
    assert set_count(1, singleton=True) == 1
    assert increase_count(1, singleton=False) == 2
    assert decrease_count(2, singleton=False) == 1
    with pytest.raises(ValueError, match="单份模式"):
        increase_count(1, singleton=True)


def test_start_count_replaces_the_saved_default() -> None:
    numbered = load_layout("numbered")
    _apply_replica_count("numbered", numbered, {"count": 2, "start": 3}, 10)
    assert [
        item.replica_name for item in numbered.desired_replicas("tools.bash", ())
    ] == [f"tools.bash-{index}" for index in range(3, 13)]

    counted = load_layout("counted")
    _apply_replica_count("counted", counted, {"count": 2, "singleton": True}, 10)
    assert len(counted.desired_replicas("tools.bash", ())) == 10

    named = load_layout("named")
    _apply_replica_count("named", named, {"names": ["alpha", "beta"]}, None)
    assert [item.label for item in named.desired_replicas("tools.bash", ())] == ["0"]
    named_ten = load_layout("named")
    _apply_replica_count("named", named_ten, {"names": ["alpha", "beta"]}, 10)
    assert [item.label for item in named_ten.desired_replicas("tools.bash", ())] == [
        str(index) for index in range(10)
    ]


def test_named_diff_opens_missing_names_and_closes_extras() -> None:
    to_start, to_stop = diff_named_replicas(["alpha", "beta"], ["beta", "gamma"])
    assert to_start == ("alpha",)
    assert to_stop == ("gamma",)
    specs = replicas_by_name("tools.bash", ["alpha", "beta"])
    assert [item.replica_name for item in specs] == [
        "tools.bash-alpha",
        "tools.bash-beta",
    ]
    assert specs[1].label == "beta"
