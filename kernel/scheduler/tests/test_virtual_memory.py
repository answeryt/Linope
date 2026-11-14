"""Logical memory: one store, a page table, and a budgeted read."""

from __future__ import annotations

import threading
from pathlib import Path

import pytest

from kernel.command.memory import run as memory_command
from kernel.environment.host_adapter import host_limit_request
from kernel.environment.policy import HostExecutionPolicy
from kernel.process.declaration import ProcessDeclaration, ResourceClaim
from kernel.process.ledger import ProcessLedger
from kernel.process.process_creat.instances import CapabilityDefinition
from kernel.process.process_manager.reaper import ProcessReaper
from kernel.process.reconcile import ProcessReconciler
from kernel.process.resource_record import ProcessResourceBook, RecordStatus
from kernel.resource.lease import ResourceLeaseManager
from kernel.resource.memory.backends import SqliteStore, configured_backend
from kernel.resource.memory.fit import fit_named_read, register_fitter, sliding_window_fit
from kernel.resource.memory.records import MemoryRow
from kernel.resource.memory.runtime import MemoryRuntime
from kernel.resource.pool import ResourcePool
from kernel.scheduler.access import remember


def _definition() -> CapabilityDefinition:
    return CapabilityDefinition(instance_id="sample.capability", module_paths=())


def test_a_read_stops_when_the_budget_is_spent() -> None:
    rows = [
        MemoryRow("message/0", "message", "user", "x" * 40, "t", 1, tokens=10),
        MemoryRow("message/1", "message", "user", "y" * 40, "t", 2, tokens=10),
        MemoryRow("message/2", "message", "user", "z" * 40, "t", 3, tokens=10),
    ]
    kept, left = fit_named_read(rows, 15)
    assert [row.real for row in kept] == ["message/0"]
    assert [row.real for row in left] == ["message/1", "message/2"]
    register_fitter(sliding_window_fit)
    try:
        advised, _rest = fit_named_read(rows, 15)
    finally:
        register_fitter(None)
    assert advised[0].real == "summary"
    assert "message/0" in advised[0].content


def test_sqlite_keeps_rows_after_a_new_runtime(tmp_path: Path) -> None:
    path = tmp_path / "memory.sqlite"
    first = MemoryRuntime(SqliteStore(path))
    assert first.append(
        resource_id="shared",
        scope="chat",
        holders=[("1", ("message",))],
        writer_pid="1",
        kind="user",
        content="remembered",
        row_state="asked",
    ) == "chat/message/0"
    second = MemoryRuntime(SqliteStore(path))
    assert second.store.row("shared", "message/0").content == "remembered"
    with pytest.raises(PermissionError):
        second.contents(
            resource_id="shared",
            scope="chat",
            pid="2",
            classes=("message",),
            selector=[(None, "message", 0, 0)],
            foreign={},
        )
    restored = second.contents(
        resource_id="shared",
        scope="chat",
        pid="2",
        classes=("message",),
        selector=[("chat", "message", 0, 0)],
        foreign={"chat": ("shared", "chat")},
    )
    assert restored[0]["content"] == "remembered"
    assert restored[0]["address"] == "chat/message/0"


def test_concurrent_appends_do_not_lose_a_row() -> None:
    runtime = MemoryRuntime()
    errors: list[BaseException] = []

    def add(number: int) -> None:
        try:
            runtime.append(
                resource_id="mem",
                scope="chat",
                holders=[("1", ("message",))],
                writer_pid="1",
                kind="user",
                content=str(number),
                row_state="asked",
            )
        except BaseException as exc:
            errors.append(exc)

    threads = [threading.Thread(target=add, args=(number,)) for number in range(12)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    rows = runtime.store.rows_of("mem", "message")
    assert errors == []
    assert len(rows) == 12
    assert len({row.seq for row in rows}) == 12


def test_releasing_the_cache_does_not_delete_the_row() -> None:
    runtime = MemoryRuntime(cache_blocks=1)
    for text in ("one", "two", "three"):
        runtime.append(
            resource_id="mem",
            scope="chat",
            holders=[("1", ("message",))],
            writer_pid="1",
            kind="user",
            content=text,
            row_state="asked",
        )
    runtime.release_resource("mem")
    assert runtime.cache_resident("mem") == ()
    assert [row.content for row in runtime.store.rows_of("mem", "message")] == ["one", "two", "three"]


def test_revoke_unloads_the_entity_and_keeps_the_stored_row(tmp_path: Path) -> None:
    pool = ResourcePool(ResourceLeaseManager())
    book = ProcessResourceBook(ProcessLedger(tmp_path / "ledger.json"))
    reconciler = ProcessReconciler(pool, book)
    process = reconciler.start(
        ProcessDeclaration(
            capability="sample.capability",
            resources=(ResourceClaim(kind="memory", identity={"scope": "chat"}),),
        ),
        definition=_definition(),
        pid=301,
    )
    grant = process.activation.grants[0]
    assert remember(pool, process.activation.grants, "user", "kept") == "chat/message/0"
    entity = pool.store.entity(grant.resource_id)
    assert entity is not None and entity.refcount == 1
    process.revoke(grant.handle)
    entity = pool.store.entity(grant.resource_id)
    assert entity is not None
    assert entity.refcount == 0
    assert entity.state is None
    assert pool.store.memory.store.row(grant.resource_id, "message/0").content == "kept"
    assert all(item.handle != grant.handle for item in book.get(process.pid).leases)


def test_reaper_accepts_a_ready_account(tmp_path: Path) -> None:
    book = ProcessResourceBook()
    book.open(7, "sample.capability")
    book.attach(7, claims=[], leases=[], room={})
    assert book.get(7).status == RecordStatus.READY
    reaper = ProcessReaper(lambda: book.close(7))
    assert reaper.reap_if_dead({"status": "ready", "pid": None, "identity": None})
    assert book.get(7).status == RecordStatus.CLOSED


def test_host_limits_are_not_memory_pages() -> None:
    request = host_limit_request(HostExecutionPolicy(max_memory_bytes=128))
    assert request["enforced_by"] == "host"
    assert request["max_memory_bytes"] == 128
    assert "page" not in request


def test_the_memory_command_records_the_chosen_backend(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    assert memory_command(["backend"])["backend"] == "memory"
    assert memory_command(["backend", "sqlite", "--path", str(tmp_path / "memory.sqlite")])["backend"] == "sqlite"
    assert configured_backend(tmp_path)[0] == "sqlite"
    assert memory_command(["backend", "memory"])["backend"] == "memory"
    assert configured_backend(tmp_path) == ("memory", "")
