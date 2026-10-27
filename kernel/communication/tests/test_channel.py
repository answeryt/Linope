"""A process's notes stay in memory. Another service is reached only by a channel the caller opened."""

import inspect
from pathlib import Path

import pytest

from kernel.communication import channel as channel_module
from kernel.communication.channel import MemoryChannel, deliver, publish
from kernel.scheduler.model_turn import turn
from kernel.process.declaration import ProcessDeclaration, ResourceClaim
from kernel.process.ledger import ProcessLedger
from kernel.process.process_creat.instances import CapabilityDefinition
from kernel.process.reconcile import ProcessReconciler
from kernel.process.resource_record import ProcessResourceBook
from kernel.resource.lease import ResourceLeaseManager
from kernel.resource.pool import ResourcePool


def test_the_kernel_does_not_name_a_transport() -> None:
    source = inspect.getsource(channel_module)
    assert "open_channel" not in source
    assert "grpc" not in source
    assert "zeromq" not in source
    assert "nats" not in source
    assert "MemoryChannel" in inspect.getsource(turn)


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
    channel = MemoryChannel(pool)
    first = channel.send("301", {"kind": "user", "content": "question", "state": "asked"})
    channel.send("301", {"kind": "tool", "content": {"success": True}, "state": "resulted"})
    rows = channel.receive("301")
    assert [row["state"] for row in rows] == ["asked", "resulted"]
    assert rows[1]["content"] == '{"success": true}'
    assert [row["content"] for row in channel.receive("301", after=int(first))] == ['{"success": true}']
    with pytest.raises(ValueError, match="Unknown state"):
        channel.send("301", {"kind": "user", "content": "question", "state": "maybe"})
    del process


class _Pipe:
    def __init__(self) -> None:
        self.sent: list[tuple[str, dict, str]] = []
        self.published: list[tuple[str, dict, str]] = []

    def send(self, to: str, message: dict, sender: str = "") -> str:
        self.sent.append((to, message, sender))
        return "7"

    def publish(self, topic: str, message: dict, sender: str = "") -> None:
        self.published.append((topic, message, sender))


def test_deliver_passes_the_address_string_through() -> None:
    pipe = _Pipe()
    body = {"kind": "user", "content": "hello", "state": "asked"}
    assert deliver(pipe, "svc-1", body, "2") == "7"
    body["content"] = "changed"
    assert pipe.sent == [("svc-1", {"kind": "user", "content": "hello", "state": "asked"}, "2")]


def test_publish_names_a_topic() -> None:
    pipe = _Pipe()
    publish(pipe, "weather", {"kind": "user", "content": "rain", "state": "asked"})
    assert pipe.published == [("weather", {"kind": "user", "content": "rain", "state": "asked"}, "")]


def test_a_missing_channel_is_refused() -> None:
    with pytest.raises(ValueError, match="^No channel selected$") as caught:
        deliver(None, "1", {"kind": "user", "content": "hello"})
    assert "open_channel" not in str(caught.value)
    with pytest.raises(ValueError, match="^No channel selected$"):
        publish(None, "weather", {"kind": "user", "content": "rain"})
