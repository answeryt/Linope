"""Command selection, then a real start of the copies that layout asked for."""

import pytest

from kernel.process.declaration import ProcessDeclaration, ResourceClaim
from kernel.process.process_manager.replica_layout.layout import ReplicaPlan
from kernel.process.process_manager.replica_layout.registry import (
    register_layout,
    unregister_layout,
)
from kernel.command import main
from kernel.process.reconcile import ProcessReconciler
from kernel.resource.definition import ResourceKind
from kernel.resource.pool import ResourcePool
from kernel.process.ledger import FileResourceStore


class _Listed:
    def desired_replicas(self, capability: str, running: tuple) -> tuple:
        del capability, running
        return ()

    def plan_replicas(self, capability: str, running: tuple) -> ReplicaPlan:
        del capability, running
        return ReplicaPlan((), (), ())


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


def test_layouts_lists_builtin_and_custom_names(tmp_path, capsys) -> None:
    path = tmp_path / "resources.json"
    register_layout("custom_demo", _Listed())
    try:
        assert main(["layouts", "--resource-store", str(path)]) == 0
        listed = capsys.readouterr().out
        assert "numbered" in listed
        assert "counted" in listed
        assert "named" in listed
        assert "custom_demo" in listed
        assert "????????????" in listed

        assert main(["layout", "numbered", "--resource-store", str(path)]) == 0
        capsys.readouterr()
        assert main(["layouts", "--resource-store", str(path)]) == 0
        selected = capsys.readouterr().out
        assert "* numbered" in selected
        assert "????????????" not in selected

        assert main(["layout", "off", "--resource-store", str(path)]) == 0
        capsys.readouterr()
        store = FileResourceStore(path)
        try:
            assert store.selected_layout() == (None, {})
        finally:
            store.close()
    finally:
        unregister_layout("custom_demo")


def test_share_list_is_selected_from_the_command(tmp_path, capsys) -> None:
    path = tmp_path / "resources.json"
    assert main(["share", "tools.bash", "context.sliding_window", "--resource-store", str(path)]) == 0
    assert "share tools.bash context.sliding_window" in capsys.readouterr().out
    store = FileResourceStore(path)
    try:
        assert store.shared_capabilities() == ("context.sliding_window", "tools.bash")
        assert store.shares_capability("tools.bash")
    finally:
        store.close()
    assert main(["share", "off", "--resource-store", str(path)]) == 0
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
    assert main(["layout", "numbered", "--resource-store", str(path)]) == 0
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
    assert main(["layout", "numbered", "--resource-store", str(path)]) == 0
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
