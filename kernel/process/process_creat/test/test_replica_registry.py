"""A custom layout is loaded by name. The reconciler does not import its class."""

from kernel.process.declaration import ProcessDeclaration
from kernel.process.process_manager.replica_layout.layout import ReplicaPlan
from kernel.process.process_manager.replica_layout.registry import (
    load_layout,
    register_layout,
    unregister_layout,
)
from kernel.process.reconcile import ProcessReconciler
from kernel.resource.pool import ResourcePool
from kernel.process.ledger import FileResourceStore

import pytest


class _Probe:
    def __init__(self) -> None:
        self.seen = False

    def desired_replicas(self, capability: str, running: tuple) -> tuple:
        del capability, running
        return ()

    def plan_replicas(self, capability: str, running: tuple) -> ReplicaPlan:
        del capability, running
        self.seen = True
        return ReplicaPlan((), (), ())


def test_off_cannot_be_registered() -> None:
    with pytest.raises(ValueError, match="保留名"):
        register_layout("off", _Probe())


def test_custom_layout_rejects_a_start_count(tmp_path) -> None:
    probe = _Probe()
    register_layout("custom_probe", probe)
    store = FileResourceStore(tmp_path / "resources.json")
    try:
        store.select_layout("custom_probe", {})
        with pytest.raises(ValueError, match="不接受"):
            ProcessReconciler(ResourcePool(store)).launch(
                ProcessDeclaration(capability="context.sliding_window"),
                replica_count=2,
            )
        assert probe.seen is False
    finally:
        unregister_layout("custom_probe")
        store.close()


def test_reconciler_runs_a_layout_it_does_not_import(tmp_path) -> None:
    probe = _Probe()
    register_layout("custom_probe", probe)
    store = FileResourceStore(tmp_path / "resources.json")
    try:
        store.select_layout("custom_probe", {})
        processes = ProcessReconciler(ResourcePool(store)).launch(
            ProcessDeclaration(capability="context.sliding_window")
        )
        assert processes == ()
        assert probe.seen is True
        assert load_layout("custom_probe") is probe
    finally:
        unregister_layout("custom_probe")
        store.close()
