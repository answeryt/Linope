import time

from kernel.process.declaration import ProcessDeclaration, ResourceClaim
from kernel.process.reconcile import ProcessReconciler
from kernel.resource.definition import ResourceKind
from kernel.resource.pool import ResourcePool
from kernel.process.ledger import FileResourceStore


def test_runtime_binds_persistent_resource_lease(tmp_path) -> None:
    store = FileResourceStore(tmp_path / "resources.json")
    declaration = ProcessDeclaration(
        capability="context.sliding_window",
        resources=(
            ResourceClaim(
                kind=ResourceKind.CONTEXT,
                identity={"window": "default"},
            ),
        ),
    )
    process = ProcessReconciler(ResourcePool(store)).start(declaration)
    process_id = process.activation.process_id
    try:
        assert process.pid is not None
        assert store.active_for(process_id)
        assert process.send({"operation": "ping"})["event"] == "pong"
    finally:
        process.stop()
        store.close()

    reopened = FileResourceStore(tmp_path / "resources.json")
    try:
        assert reopened.active_for(process_id) == ()
    finally:
        reopened.close()


def test_idle_process_does_not_rewrite_the_ledger(tmp_path) -> None:
    path = tmp_path / "resources.json"
    store = FileResourceStore(path)
    declaration = ProcessDeclaration(
        capability="context.sliding_window",
        resources=(
            ResourceClaim(
                kind=ResourceKind.CONTEXT,
                identity={"window": "default"},
            ),
        ),
    )
    process = ProcessReconciler(ResourcePool(store)).start(declaration)
    try:
        assert process.send({"operation": "ping"})["event"] == "pong"
        time.sleep(0.2)
        stamp = path.stat().st_mtime_ns
        time.sleep(0.45)
        assert path.stat().st_mtime_ns == stamp
    finally:
        process.stop()
        store.close()
