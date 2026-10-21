"""A message reaches another process through the channel the user chose."""

import time
from pathlib import Path

import pytest

from kernel.communication.channel import MemoryChannel, channel_names, needs, open_channel
from kernel.process.declaration import ProcessDeclaration, ResourceClaim
from kernel.process.ledger import ProcessLedger
from kernel.process.process_creat.instances import CapabilityDefinition
from kernel.process.reconcile import ProcessReconciler
from kernel.process.resource_record import ProcessResourceBook
from kernel.resource.lease import ResourceLeaseManager
from kernel.resource.pool import ResourcePool


def test_every_named_channel_is_registered() -> None:
    assert {"memory", "grpc", "nats", "zeromq"} <= set(channel_names())


def test_an_unknown_channel_lists_the_known_ones() -> None:
    with pytest.raises(ValueError, match="memory"):
        open_channel("pigeon")


def test_a_missing_library_names_the_package() -> None:
    with pytest.raises(RuntimeError, match="pip install some-package"):
        needs("some-package", "linope_module_that_is_not_installed")


def test_memory_channel_reads_every_row_after_a_seq(tmp_path: Path) -> None:
    pool = ResourcePool(ResourceLeaseManager())
    reconciler = ProcessReconciler(pool, ProcessResourceBook(ProcessLedger(tmp_path / "ledger.json")))
    process = reconciler.start(
        ProcessDeclaration(
            capability="sample.capability",
            resources=(ResourceClaim(kind="memory", identity={"scope": "chat"}),),
        ),
        definition=CapabilityDefinition(instance_id="sample.capability", module_paths=()),
        pid=301,
    )
    channel = open_channel("memory", pool=pool)
    assert isinstance(channel, MemoryChannel)
    first = channel.send("301", {"kind": "user", "content": "问", "state": "asked"})
    channel.send("301", {"kind": "tool", "content": {"success": True}, "state": "resulted"})
    rows = channel.receive("301")
    assert [row["state"] for row in rows] == ["asked", "resulted"]
    assert rows[1]["content"] == '{"success": true}'
    assert [row["content"] for row in channel.receive("301", after=int(first))] == ['{"success": true}']
    with pytest.raises(ValueError, match="不认识的状态"):
        channel.send("301", {"kind": "user", "content": "问", "state": "maybe"})
    del process


def _wait(channel, me: str, count: int) -> list[dict]:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        rows = channel.receive(me)
        if len(rows) >= count:
            return rows
        time.sleep(0.05)
    return channel.receive(me)


def test_zeromq_delivers_to_the_bound_process() -> None:
    pytest.importorskip("zmq")
    channel = open_channel("zeromq")
    try:
        channel.listen("7")
        channel.send("7", {"kind": "user", "content": "你好", "state": "asked"}, sender="1")
        rows = _wait(channel, "7", 1)
        assert rows[0]["content"] == "你好"
        assert rows[0]["sender"] == "1"
        assert rows[0]["seq"] == 1
    finally:
        channel.close()


def test_grpc_waits_for_the_receivers_seq() -> None:
    pytest.importorskip("grpc")
    channel = open_channel("grpc")
    try:
        channel.listen("8")
        assert channel.send("8", {"kind": "tool", "content": "{}", "state": "resulted"}) == "1"
        assert channel.receive("8")[0]["state"] == "resulted"
    finally:
        channel.close()
