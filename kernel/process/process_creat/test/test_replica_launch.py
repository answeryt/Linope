"""Command selection, then a real start of the copies that layout asked for."""

import pytest

from kernel.process.declaration import ProcessDeclaration, ResourceClaim
from kernel.process.process_manager.replica_layout.layout import ReplicaPlan
from kernel.command import main
from kernel.process.reconcile import ProcessReconciler
from kernel.resource.definition import ResourceKind
from kernel.resource.pool import ResourcePool
from kernel.process.ledger import FileResourceStore


def _declaration() -> ProcessDeclaration:
    return ProcessDeclaration(
        capability="context.sliding_window",
        resources=(
            ResourceClaim(
                kind=ResourceKind.CONTEXT,
                identity={"window": "default"},
            ),
        ),
    )

def test_share_list_is_selected_from_the_command(tmp_path, capsys) -> None:
    path = tmp_path / "resources.json"
    assert main(["process", "share", "tools.bash", "context.sliding_window", "--resource-store", str(path)]) == 0
    assert "share tools.bash context.sliding_window" in capsys.readouterr().out
    store = FileResourceStore(path)
    try:
        assert store.shared_capabilities() == ("context.sliding_window", "tools.bash")
        assert store.shares_capability("tools.bash")
    finally:
        store.close()
    assert main(["process", "share", "off", "--resource-store", str(path)]) == 0
    store = FileResourceStore(path)
    try:
        assert store.shared_capabilities() == ()
    finally:
        store.close()


def test_shared_capability_uses_one_entity_across_processes(tmp_path) -> None:
    path = tmp_path / "resources.json"
    store = FileResourceStore(path)
    store.share_capabilities(("context.sliding_window",))
    store.select_layout("numbered", {"count": 2, "start": 0})
    started: list = []
    try:
        started.extend(
            ProcessReconciler(ResourcePool(store)).launch(_declaration(), replica_count=2)
        )
        assert len(started) == 2
        resource_ids = {
            lease.resource_id
            for process in started
            for lease in store.active_for(process.activation.process_id)
        }
        assert len(resource_ids) == 1
    finally:
        for process in started:
            process.stop()
        store.close()


def test_unshared_capability_gets_one_entity_per_process(tmp_path) -> None:
    path = tmp_path / "resources.json"
    assert main(["layout", "use", "numbered", "--resource-store", str(path)]) == 0
    store = FileResourceStore(path)
    started: list = []
    try:
        started.extend(
            ProcessReconciler(ResourcePool(store)).launch(_declaration(), replica_count=2)
        )
        resource_ids = {
            lease.resource_id
            for process in started
            for lease in store.active_for(process.activation.process_id)
        }
        assert len(resource_ids) == 2
    finally:
        for process in started:
            process.stop()
        store.close()


def test_numbered_layout_defaults_to_one_and_count_starts_two(tmp_path) -> None:
    path = tmp_path / "resources.json"
    assert main(["layout", "use", "numbered", "--resource-store", str(path)]) == 0
    store = FileResourceStore(path)
    started: list = []
    try:
        started.extend(ProcessReconciler(ResourcePool(store)).launch(_declaration()))
        assert len(started) == 1
        assert {
            row["replica_name"] for row in store.running_replicas("context.sliding_window")
        } == {"context.sliding_window-0"}
        assert started[0].send({"operation": "ping"})["event"] == "pong"
    finally:
        for process in started:
            process.stop()
        store.close()

    store = FileResourceStore(path)
    started = []
    try:
        started.extend(
            ProcessReconciler(ResourcePool(store)).launch(_declaration(), replica_count=2)
        )
        assert len(started) == 2
        names = {
            row["replica_name"] for row in store.running_replicas("context.sliding_window")
        }
        assert names == {
            "context.sliding_window-0",
            "context.sliding_window-1",
        }
        assert len({process.pid for process in started}) == 2
        for process in started:
            assert process.send({"operation": "ping"})["event"] == "pong"
    finally:
        for process in started:
            process.stop()
        store.close()

    assert main(["layout", "off", "--resource-store", str(path)]) == 0
    store = FileResourceStore(path)
    started = []
    try:
        with pytest.raises(ValueError, match="还没选择布局"):
            ProcessReconciler(ResourcePool(store)).launch(_declaration(), replica_count=2)
        started.extend(ProcessReconciler(ResourcePool(store)).launch(_declaration()))
        assert len(started) == 1
        assert started[0].send({"operation": "ping"})["event"] == "pong"
    finally:
        for process in started:
            process.stop()
        store.close()


def test_a_smaller_replica_count_marks_the_extra_copy_to_stop(tmp_path) -> None:
    path = tmp_path / "resources.json"
    assert main(["layout", "use", "numbered", "--resource-store", str(path)]) == 0
    store = FileResourceStore(path)
    started: list = []
    try:
        started.extend(
            ProcessReconciler(ResourcePool(store)).launch(_declaration(), replica_count=2)
        )
        assert len(started) == 2
        again = ProcessReconciler(ResourcePool(store)).launch(_declaration(), replica_count=1)
        assert again == ()
        marked = [
            (store.get_process(process.activation.process_id) or {}).get("desired")
            for process in started
        ]
        assert marked.count("stop") == 1
    finally:
        for process in started:
            process.stop()
        store.close()
