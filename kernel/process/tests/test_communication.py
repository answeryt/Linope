"""Channel registration, selection, and peer ping over each built-in transport."""

import os
import shutil
import socket
from urllib.parse import urlparse

import pytest

from kernel.process.communication.channel import ChannelOpen
from kernel.process.communication.ledger.mailbox import LedgerChannel
from kernel.process.communication.directory import select_channel, selected_channel
from kernel.process.communication.registry import (
    channel_names,
    load_channel,
    register_channel,
    unregister_channel,
)
from kernel.process.declaration import ProcessDeclaration, ResourceClaim
from kernel.command import main
from kernel.process.reconcile import ProcessReconciler
from kernel.resource.definition import ResourceKind
from kernel.resource.pool import ResourcePool
from kernel.process.hypermedia.observation import deliver_observation
from kernel.process.hypermedia.link import Link
from kernel.process.hypermedia.representation_json import file_resource_payload
from kernel.process.ledger import FileResourceStore
from kernel.resource.memory.page import Page, PageState

_BUILTINS = ("ledger", "zeromq", "grpc", "nats")


class _Quiet:
    def bind(self, process_id: str) -> None:
        del process_id

    def submit(self, process_id: str, body: dict, sender_id: str | None = None) -> str:
        del process_id, body, sender_id
        return "ticket"

    def take(self, process_id: str):
        del process_id
        return None

    def complete(self, request_id: str, reply: dict) -> None:
        del request_id, reply

    def lookup(self, request_id: str):
        del request_id
        return None

    def close(self) -> None:
        return None


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


def test_custom_channel_registers_and_builtins_stay() -> None:
    register_channel("custom_probe", lambda opened: _Quiet())
    try:
        assert "custom_probe" in channel_names()
        opened = ChannelOpen(store=object(), store_path="", settings={})
        channel = load_channel("custom_probe", opened)
        assert channel.submit("process", {"operation": "ping"}) == "ticket"
        with pytest.raises(ValueError, match="内置通道不能取消登记"):
            unregister_channel("ledger")
        for name in _BUILTINS:
            with pytest.raises(ValueError):
                unregister_channel(name)
    finally:
        unregister_channel("custom_probe")
    assert "custom_probe" not in channel_names()
    with pytest.raises(KeyError, match="未知通道"):
        load_channel("custom_probe", ChannelOpen(store=object(), store_path="", settings={}))


def test_channels_command_selects_and_clears(tmp_path, capsys) -> None:
    path = tmp_path / "resources.json"
    assert main(["channels", "--resource-store", str(path)]) == 0
    listed = capsys.readouterr().out
    for name in _BUILTINS:
        assert name in listed
    assert "未选择，将使用 ledger" in listed

    assert main(["channel", "zeromq", "--resource-store", str(path)]) == 0
    capsys.readouterr()
    assert main(["channels", "--resource-store", str(path)]) == 0
    assert "* zeromq" in capsys.readouterr().out
    assert selected_channel(path)[0] == "zeromq"

    assert main(["channel", "missing", "--resource-store", str(path)]) == 1
    assert "未知通道" in capsys.readouterr().err

    assert main(["channel", "nats", "--resource-store", str(path)]) == 0
    capsys.readouterr()
    assert selected_channel(path) == ("nats", {"url": "nats://127.0.0.1:4222"})

    assert main(["channel", "off", "--resource-store", str(path)]) == 0
    capsys.readouterr()
    assert selected_channel(path) == (None, {})


def test_empty_mailbox_look_does_not_rewrite_the_ledger(tmp_path) -> None:
    path = tmp_path / "resources.json"
    store = FileResourceStore(path, reap=False)
    try:
        store.register_process("p1", "model.openai_chat_model", 1, "running")
        before = path.read_bytes()
        stamp = path.stat().st_mtime_ns
        channel = LedgerChannel(ChannelOpen(store=store, store_path=str(path)))
        assert channel.claim("p1", "worker", 30) is None
        assert channel.take("p1") is None
        assert store.peek_process("p1")["status"] == "running"
        assert path.read_bytes() == before
        assert path.stat().st_mtime_ns == stamp
    finally:
        store.close()


def test_taking_an_observation_leaves_the_page_state(tmp_path) -> None:
    path = tmp_path / "resources.json"
    store = FileResourceStore(path, reap=False)
    try:
        page = Page(address="notes.md", size=4, state=PageState.RESIDENT)
        link = Link(relation="self", resource_id="notes.md", handle="ab" * 16)
        store.save_page(page, link)
        payload = file_resource_payload(
            page.address,
            link.handle,
            page.state.value,
            "http://127.0.0.1:9",
        )
        channel = LedgerChannel(ChannelOpen(store=store, store_path=str(path)))
        deliver_observation(channel, "p1", payload)
        deliver_observation(channel, "p2", payload)
        first = channel.take("p1")
        second = channel.claim("p2", "worker", 30)
        assert first["body"]["operation"] == "observe"
        assert second["body"]["href"] == payload["_links"]["self"]["href"]
        assert store.page_at("notes.md").state is PageState.RESIDENT
    finally:
        store.close()


def test_channel_off_starts_on_the_ledger(tmp_path) -> None:
    path = tmp_path / "resources.json"
    assert main(["channel", "off", "--resource-store", str(path)]) == 0
    store = FileResourceStore(path)
    process = ProcessReconciler(ResourcePool(store)).start(_declaration())
    try:
        assert process.activation.payload()["communication"]["name"] == "ledger"
        assert process.send({"operation": "ping"})["event"] == "pong"
    finally:
        process.stop()
        store.close()


def test_zeromq_ping_between_peers(tmp_path) -> None:
    pytest.importorskip("zmq")
    _ping_over(tmp_path, "zeromq", {})


def test_grpc_ping_between_peers(tmp_path) -> None:
    pytest.importorskip("grpc")
    _ping_over(tmp_path, "grpc", {})


def test_nats_ping_between_peers(tmp_path) -> None:
    pytest.importorskip("nats")
    url = os.environ.get("NATS_URL", "nats://127.0.0.1:4222")
    if not os.environ.get("NATS_URL") and shutil.which("nats-server") is None:
        pytest.skip("没有 nats-server")
    if not _nats_listening(url):
        pytest.skip("NATS 服务器没有在监听")
    _ping_over(tmp_path, "nats", {"url": url})


def _ping_over(tmp_path, name: str, settings: dict) -> None:
    path = tmp_path / "resources.json"
    select_channel(path, name, settings)
    store = FileResourceStore(path)
    process = ProcessReconciler(ResourcePool(store)).start(_declaration())
    try:
        assert process.activation.payload()["communication"]["name"] == name
        assert process.send({"operation": "ping"}, timeout=20)["event"] == "pong"
    finally:
        process.stop()
        store.close()


def _nats_listening(url: str) -> bool:
    parsed = urlparse(url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 4222
    try:
        with socket.create_connection((host, port), timeout=0.3):
            return True
    except OSError:
        return False
