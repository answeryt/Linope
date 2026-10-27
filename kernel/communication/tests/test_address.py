"""Each process maps its own addresses onto one shared memory."""

from pathlib import Path

import pytest

from kernel.communication.address import (
    admit,
    memory_contents,
    remember,
)
from kernel.process.declaration import ProcessDeclaration, ResourceClaim
from kernel.process.ledger import ProcessLedger
from kernel.process.process_creat.instances import CapabilityDefinition
from kernel.process.reconcile import ProcessReconciler
from kernel.process.resource_record import ProcessResourceBook
from kernel.resource.lease import ResourceLeaseManager
from kernel.resource.pool import ResourcePool


def _definition() -> CapabilityDefinition:
    return CapabilityDefinition(instance_id="sample.capability", module_paths=())


def _memory(space: str, scope: str = "chat") -> ProcessDeclaration:
    return ProcessDeclaration(
        capability="sample.capability",
        resources=(
            ResourceClaim(
                kind="memory",
                identity={"scope": scope},
                call_params={"space": space},
            ),
        ),
    )


def _open(tmp_path: Path):
    ledger = ProcessLedger(tmp_path / "ledger.json")
    book = ProcessResourceBook(ledger)
    pool = ResourcePool(ResourceLeaseManager())
    return pool, ProcessReconciler(pool, book)


def _reals(pool, process, selector: str = "") -> list[str]:
    contents = memory_contents(pool, process.activation.grants, selector)
    assert contents is not None
    return [item["real"] for item in contents["items"]]


def test_address_zero_can_differ_and_still_share_one_real_name(tmp_path: Path) -> None:
    pool, reconciler = _open(tmp_path)
    first = reconciler.start(
        _memory("message"),
        definition=_definition(),
        shared=("memory",),
        pid=201,
    )
    assert remember(pool, first.activation.grants, "user", "first line") == "chat/message/0"
    second = reconciler.start(
        _memory("message"),
        definition=_definition(),
        shared=("memory",),
        pid=202,
    )
    assert remember(pool, first.activation.grants, "user", "second line") == "chat/message/1"

    first_items = memory_contents(pool, first.activation.grants)["items"]
    second_items = memory_contents(pool, second.activation.grants)["items"]
    assert first_items[0]["address"] == "message/0"
    assert second_items[0]["address"] == "message/0"
    assert first_items[0]["real"] != second_items[0]["real"]
    assert first_items[1]["real"] == second_items[0]["real"]
    assert first_items[1]["content"] == "second line"
    assert second_items[0]["content"] == "second line"
    assert first_items[0]["time"]
    assert second_items[0]["time"] >= first_items[0]["time"]
    saved = (tmp_path / "ledger.json").read_text(encoding="utf-8")
    assert "first line" not in saved
    assert "second line" not in saved
    first.stop()
    second.stop()


def test_a_class_outside_the_space_is_refused(tmp_path: Path) -> None:
    pool, reconciler = _open(tmp_path)
    process = reconciler.start(
        _memory("artifact"),
        definition=_definition(),
        shared=("memory",),
        pid=203,
    )
    with pytest.raises(PermissionError):
        remember(pool, process.activation.grants, "user", "should not see")
    assert remember(pool, process.activation.grants, "tool", "result") == "chat/artifact/0"
    assert _reals(pool, process) == ["artifact/0"]
    with pytest.raises(PermissionError):
        memory_contents(pool, process.activation.grants, "message")
    with pytest.raises(PermissionError):
        memory_contents(pool, process.activation.grants, "artifact/3-7")
    process.stop()


def test_a_written_range_reads_only_those_addresses(tmp_path: Path) -> None:
    pool, reconciler = _open(tmp_path)
    process = reconciler.start(_memory("message,task"), definition=_definition(), pid=204)
    for text in ("A", "B", "C"):
        remember(pool, process.activation.grants, "user", text)
    remember(pool, process.activation.grants, "other", "task")
    contents = memory_contents(pool, process.activation.grants, "message/0-1 task/0")
    assert [item["content"] for item in contents["items"]] == ["A", "B", "task"]
    assert [item["address"] for item in contents["items"]] == [
        "message/0",
        "message/1",
        "task/0",
    ]
    process.stop()


def test_the_old_name_check_still_refuses_another_scope(tmp_path: Path) -> None:
    _pool, reconciler = _open(tmp_path)
    process = reconciler.start(_memory("message"), definition=_definition(), pid=205)
    record = reconciler.book.get(process.pid)
    admit(record.leases, "chat")
    with pytest.raises(PermissionError):
        admit(record.leases, "other")
    process.stop()


def test_a_named_address_stays_inside_the_pointer_space(tmp_path: Path) -> None:
    from kernel.scheduler.memory_space import PointerSpace, authorize_resource

    pool, reconciler = _open(tmp_path)
    chat = reconciler.start(_memory("message", "chat"), definition=_definition(), pid=206)
    hello = reconciler.start(_memory("message", "hello"), definition=_definition(), pid=207)
    remember(pool, chat.activation.grants, "user", "hello")
    remember(pool, hello.activation.grants, "user", "hello")

    own = memory_contents(pool, chat.activation.grants)
    assert [item["content"] for item in own["items"]] == ["hello"]
    assert own["items"][0]["name"] == "chat"
    named = memory_contents(pool, chat.activation.grants, "chat/message/0")
    assert [item["content"] for item in named["items"]] == ["hello"]

    with pytest.raises(PermissionError, match="address space"):
        memory_contents(pool, chat.activation.grants, "hello/message/0")
    with pytest.raises(PermissionError, match="address space"):
        memory_contents(pool, chat.activation.grants, "hello")
    with pytest.raises(PermissionError, match="address space"):
        memory_contents(pool, chat.activation.grants, "missing/message/0")
    with pytest.raises(PermissionError):
        memory_contents(pool, chat.activation.grants, "hello/artifact/0")
    with pytest.raises(PermissionError, match="address space"):
        authorize_resource(chat.activation.grants, hello.activation.grants[0].resource_id)

    rebuilt = PointerSpace.from_grants(chat.pid, chat.activation.grants)
    assert rebuilt.own() is not None
    assert rebuilt.own().scope == "chat"
    assert rebuilt.own().classes == ("message",)
    assert rebuilt.for_scope("hello") is None
    chat.stop()
    hello.stop()
