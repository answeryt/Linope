"""Transports live outside the kernel. A caller imports and opens one."""

import time

import pytest

from bindings.support import needs
from bindings.zeromq_channel import ZeroMqChannel


def test_a_missing_library_names_the_package() -> None:
    with pytest.raises(RuntimeError, match="pip install some-package"):
        needs("some-package", "linope_module_that_is_not_installed")


def _wait(channel, me: str, count: int) -> list[dict]:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        rows = channel.receive(me)
        if len(rows) >= count:
            return rows
        time.sleep(0.05)
    return channel.receive(me)


def test_zeromq_delivers_to_the_bound_address() -> None:
    pytest.importorskip("zmq")
    channel = ZeroMqChannel()
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
    from bindings.grpc_channel import GrpcChannel

    channel = GrpcChannel()
    try:
        channel.listen("8")
        assert channel.send("8", {"kind": "tool", "content": "{}", "state": "resulted"}) == "1"
        assert channel.receive("8")[0]["state"] == "resulted"
    finally:
        channel.close()
