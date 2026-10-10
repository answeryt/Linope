from kernel.process.declaration import ProcessDeclaration, ResourceClaim
from kernel.process.process_manager.lifecycle import ProcessStatus
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
                limits={"context_budget": 1024},
            ),
        ),
    )


def test_capability_process_has_its_own_pid_and_lifecycle(tmp_path) -> None:
    pool = ResourcePool(FileResourceStore(tmp_path / "resources.json"))
    process = ProcessReconciler(pool).start(_declaration())
    try:
        assert process.pid is not None
        assert process.is_alive
        assert pool.store.active_for(process.activation.process_id)
        assert process.send({"operation": "ping"})["event"] == "pong"
        grant = process.activation.resource_context.payload()["grants"][0]
        assert "resource_id" not in grant
        assert set(grant) == {"handle", "kind", "limits", "call_params"}
        process.stop()
        assert process.status == ProcessStatus.STOPPED
        assert not process.is_alive
        assert pool.store.active_for(process.activation.process_id) == ()
    finally:
        if process.status not in {ProcessStatus.STOPPED, ProcessStatus.FAILED}:
            process.stop()
        pool.store.close()


def test_revoke_notifies_the_child(tmp_path) -> None:
    pool = ResourcePool(FileResourceStore(tmp_path / "resources.json"))
    process = ProcessReconciler(pool).start(_declaration())
    handle = process.activation.resource_context.grants[0].handle
    try:
        reply = process.revoke(handle)
        assert reply["handle"] == handle
        assert pool.store.active_for(process.activation.process_id) == ()
    finally:
        process.stop()
        pool.store.close()
