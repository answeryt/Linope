"""One account per process: identity, sharing, once, and the ledger copy."""

from pathlib import Path

import pytest

from kernel.process.declaration import ProcessDeclaration, ResourceClaim
from kernel.process.process_creat.instances import CapabilityDefinition
from kernel.process.ledger import ProcessLedger
from kernel.process.process_manager.reaper import ProcessReaper
from kernel.process.reconcile import ProcessReconciler
from kernel.process.resource_record import ProcessResourceBook, RecordStatus
from kernel.resource.lease import ResourceLeaseManager
from kernel.resource.pool import ResourcePool
from kernel.resource.resource_contract import (
    ResourceContract,
    register,
    require,
    unregister,
)


def _declaration(*claims: ResourceClaim) -> ProcessDeclaration:
    return ProcessDeclaration(capability="sample.capability", resources=claims)


def _definition() -> CapabilityDefinition:
    return CapabilityDefinition(instance_id="sample.capability", module_paths=())


def _book(tmp_path: Path) -> tuple[ProcessResourceBook, ResourcePool, ProcessReconciler]:
    ledger = ProcessLedger(tmp_path / "ledger.json")
    book = ProcessResourceBook(ledger)
    pool = ResourcePool(ResourceLeaseManager())
    return book, pool, ProcessReconciler(pool, book)


def test_one_process_has_one_record_and_its_handles(tmp_path: Path) -> None:
    book, _pool, reconciler = _book(tmp_path)
    process = reconciler.start(
        _declaration(ResourceClaim(kind="tool", identity={"id": "files"})),
        definition=_definition(),
    )
    process_id = process.activation.process_id
    record = book.get(process_id)
    assert record is not None
    assert record.status == RecordStatus.READY
    assert book.handles_for(process_id) == tuple(
        grant.handle for grant in process.activation.grants
    )
    saved = ProcessLedger(tmp_path / "ledger.json").read()
    assert saved[0]["process_id"] == process_id
    assert "limits" not in saved[0]


def test_another_process_cannot_use_the_handle(tmp_path: Path) -> None:
    book, pool, reconciler = _book(tmp_path)
    first = reconciler.start(
        _declaration(ResourceClaim(kind="tool", identity={"id": "files"})),
        definition=_definition(),
    )
    second = reconciler.start(
        _declaration(ResourceClaim(kind="tool", identity={"id": "files"})),
        definition=_definition(),
    )
    handle = first.activation.grants[0].handle
    with pytest.raises(PermissionError):
        pool.authorize(handle, second.activation.process_id)
    pool.authorize(handle, first.activation.process_id)


def test_share_is_only_the_named_kind(tmp_path: Path) -> None:
    _book_unused, _pool, reconciler = _book(tmp_path)
    declaration = _declaration(
        ResourceClaim(kind="model", identity={"provider": "openai", "id": "gpt-4o"}),
        ResourceClaim(kind="memory", identity={"scope": "chat"}),
    )
    shared = reconciler.launch(
        declaration,
        definition=_definition(),
        shared=("model",),
        replica_count=2,
    )
    separate = reconciler.launch(declaration, definition=_definition(), replica_count=2)
    assert shared[0].activation.grants[0].resource_id == shared[1].activation.grants[0].resource_id
    assert shared[0].activation.grants[1].resource_id != shared[1].activation.grants[1].resource_id
    assert (
        separate[0].activation.grants[0].resource_id
        != separate[1].activation.grants[0].resource_id
    )
    shared[0].stop()
    assert reconciler.pool.store.entity(shared[0].activation.grants[0].resource_id).refcount == 1
    shared[1].stop()
    assert reconciler.pool.store.entity(shared[1].activation.grants[0].resource_id).refcount == 0


def test_startup_failure_discards_the_record(tmp_path: Path) -> None:
    book, _pool, reconciler = _book(tmp_path)
    with pytest.raises(ValueError):
        reconciler.start(
            _declaration(ResourceClaim(kind="model", identity={"id": "gpt-4o"})),
            definition=_definition(),
        )
    assert book.get(next(iter(book._records), "")) is None
    assert ProcessLedger(tmp_path / "ledger.json").read() == []


def test_once_closes_the_record_and_a_call_adds_no_line(tmp_path: Path) -> None:
    book, _pool, reconciler = _book(tmp_path)
    process = reconciler.start(
        _declaration(ResourceClaim(kind="network", identity={"channel": "ledger"})),
        definition=_definition(),
    )
    before = len(book.get(process.activation.process_id).leases)
    process.submit({"operation": "ping"})
    assert len(book.get(process.activation.process_id).leases) == before
    process.stop()
    assert book.get(process.activation.process_id).status == RecordStatus.CLOSED


def test_reaper_closes_a_dead_process(tmp_path: Path) -> None:
    book, _pool, reconciler = _book(tmp_path)
    process = reconciler.start(
        _declaration(ResourceClaim(kind="tool", identity={"id": "files"})),
        definition=_definition(),
    )
    process_id = process.activation.process_id
    reaper = ProcessReaper(lambda: book.close(process_id))
    assert reaper.reap_if_dead({"status": "running", "pid": None, "identity": None})
    assert book.get(process_id).status == RecordStatus.CLOSED


def test_reaping_a_saved_book_does_not_need_a_live_service(tmp_path: Path) -> None:
    book, _pool, reconciler = _book(tmp_path)
    process = reconciler.start(
        _declaration(ResourceClaim(kind="tool", identity={"id": "files"})),
        definition=_definition(),
    )
    process.stop()
    from kernel.services.assembly import _reap_dead

    _reap_dead(book)
    assert book.get(process.activation.process_id).status == RecordStatus.CLOSED


def test_a_new_kind_registers_without_a_pool_change(tmp_path: Path) -> None:
    register(ResourceContract("widget", ("name",)))
    try:
        _book_unused, pool, reconciler = _book(tmp_path)
        process = reconciler.start(
            _declaration(ResourceClaim(kind="widget", identity={"name": "one"})),
            definition=_definition(),
        )
        assert process.activation.grants[0].kind == "widget"
        pool.authorize(process.activation.grants[0].handle, process.activation.process_id)
    finally:
        unregister("widget")
    with pytest.raises(ValueError, match="不认识的资源"):
        require("widget")


def test_memory_scope_is_the_only_address_space(tmp_path: Path) -> None:
    from kernel.resource.address import admit, address_scope

    _book_unused, _pool, reconciler = _book(tmp_path)
    process = reconciler.start(
        _declaration(ResourceClaim(kind="memory", identity={"scope": "chat"})),
        definition=_definition(),
    )
    record = _book_unused.get(process.activation.process_id)
    assert address_scope(record.leases) == "chat"
    admit(record.leases, "chat")
    with pytest.raises(PermissionError):
        admit(record.leases, "other")
    state = reconciler.pool.store.entity(process.activation.grants[0].resource_id).state
    assert state["address_space"]["scope"] == "chat"
    ledger = ProcessLedger(tmp_path / "ledger.json")
    with pytest.raises(ValueError, match="不该保存"):
        ledger.write(
            [
                {
                    "process_id": "p",
                    "capability_id": "c",
                    "status": "ready",
                    "claims": [],
                    "leases": [],
                    "room": {},
                    "pid": 0,
                    "started": "",
                    "reply": "the model said hello",
                }
            ]
        )
